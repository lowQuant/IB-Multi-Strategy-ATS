# utils.py

import pandas as pd
import yfinance as yf
from ib_async import *
from arcticdb import QueryBuilder

import math, datetime

class FXCache:
    def __init__(self, ib_client):
        self.ib = ib_client
        self.fx_cache = {}

    def get_fx_rate(self, currency, base_currency):
        # Check if the rate is already cached
        if (currency, base_currency) in self.fx_cache:
            return self.fx_cache[(currency, base_currency)]

        if currency == base_currency:
            self.fx_cache[(currency, base_currency)] = 1.0
        else:
            fx_pair = Forex(base_currency + currency)
            self.ib.reqMarketDataType(4)  # Dynamic data
            self.ib.qualifyContracts(fx_pair)
            rate = self.ib.reqMktData(fx_pair, '', False, False)
            self.ib.sleep(0.2)  # small delay for data fetch

            if type(rate.marketPrice()) == float and not math.isnan(rate.marketPrice()):
                self.fx_cache[(currency, base_currency)] = rate.marketPrice()
            else:
                # Fallback if no live data
                ticker = f"{base_currency}{currency}=X"
                try:
                    rate = yf.Ticker(ticker).info['ask']
                    self.fx_cache[(currency, base_currency)] = rate
                except:
                    self.fx_cache[(currency, base_currency)] = 1.0  # Default FX rate if all else fails

        return self.fx_cache[(currency, base_currency)]

    def convert_marketValue_to_base(self, df, base_currency):
        """Converts all market values in the DataFrame to the base currency."""
        df['fx_rate'] = df['currency'].map(lambda x: self.get_fx_rate(x, base_currency))
        df['marketValue_base'] = df['marketValue'] / df['fx_rate']
        return df

def create_position_dict(portfoliomanager,item):
    return {'symbol': item.contract.symbol,
            'asset class': get_asset_class(item),
            'position':item.position,
            'timestamp': datetime.datetime.now(),#.strftime('%Y-%m-%d %H:%M:%S'),
            '% of nav':(item.marketValue/portfoliomanager.total_equity) * 100,
            'averageCost': item.averageCost,
            'marketPrice': item.marketPrice,
            'pnl %': get_pnl(item) * 100,
            'strategy': '',
            'contract': item.contract,
            'trade': '',
            'trade_context': '',
            'open_dt':datetime.date.today().isoformat(),
            'close_dt': '',
            'deleted': False,
            'delete_dt': '',
            'marketValue': item.marketValue,
            'unrealizedPNL': item.unrealizedPNL,
            'currency':item.contract.currency,
            'realizedPNL': item.realizedPNL,
            'account': item.account,
            'marketValue_base': 0.0,
            'fx_rate': portfoliomanager.fx_cache.get_fx_rate(item.contract.currency, portfoliomanager.base)}

def create_trade_entry(portfoliomanager, strategy_symbol,trade):
    '''Function to create a Dataframe from ib_insync's trade object
        for further processing in our arcticDB.'''
    fx_rate = portfoliomanager.fx_cache.get_fx_rate(trade.contract.currency,portfoliomanager.base)
    cost = trade.orderStatus.avgFillPrice
    qty =  trade.order.totalQuantity *(-1) if trade.order.action == 'SELL' else trade.order.totalQuantity 
    value = cost*qty
    value_base = value / fx_rate
    
    try:
        trade_dict = {'timestamp': datetime.datetime.now(),
        'symbol': trade.contract.symbol,
        'asset class': trade.contract.secType,
        'position': qty,
        '% of nav': (value_base / portfoliomanager.total_equity) *100  , # to be calculated
        'averageCost': cost,
        'marketPrice': cost,
        'pnl %': 0.0, # to be calculated
        'strategy': strategy_symbol,
        'contract': str(trade.contract),
        'trade': str(trade),
        'trade_context': str(trade),
        'open_dt':datetime.date.today().isoformat(),
        'close_dt': '',
        'deleted': False,
        'delete_dt': '',
        'marketValue': value, # to be calculated
        'unrealizedPNL': 0.0, # to be calculated
        'currency':trade.contract.currency,
        'realizedPNL': 0.0, # to be calculated
        'account': trade.fills[0].execution.acctNumber,
        'marketValue_base': value_base, # to be calculated
        'fx_rate': fx_rate}
    except Exception as e:
        print(f"Error processing trade: {e}")

    trade_df = pd.DataFrame([trade_dict])
    trade_df.set_index('timestamp', inplace=True)
    return trade_df


def get_asset_class(item):
    if item.contract.secType == "OPT":
        return "Call" if item.contract.right == "C" else "Put" + " " + str(item.contract.strike) + " " + item.contract.lastTradeDateOrContractMonth
    elif item.contract.secType == "FUT":
        return item.contract.localSymbol + " " + item.contract.lastTradeDateOrContractMonth
    else:
        return item.contract.secType
        
def get_pnl(item):
    if item.contract.secType == "OPT":
        if item.position < 0:
            pnl = ((item.marketPrice/(item.averageCost/100)) -1) * (-1)
        else:
            pnl = ( (item.marketPrice/ (item.averageCost/100)) -1)
    elif item.contract.secType == "FUT":
        pnl = ((item.marketPrice/(item.averageCost/int(item.contract.multiplier))) -1)
        pnl = pnl *(-1) if item.position < 0 else pnl
    elif item.contract.secType == "STK":
        pnl = ((item.marketPrice/(item.averageCost)) -1)
        pnl = pnl *(-1) if item.position < 0 else pnl
    return pnl

def calculate_pnl(market_price, average_cost, position, contract=None):
    """
    Calculate PNL percentage based on market price, average cost, and position.
    For options and futures, contract details are considered for multiplier effect.

    Parameters:
    - market_price: The current market price of the asset.
    - average_cost: The average cost of the asset.
    - position: The quantity of the asset.
    - contract: The contract object containing details like type and multiplier.
    """
    pnl_percent = 0
    if contract is not None:
        if isinstance(contract, Stock):
            pnl = ((market_price / average_cost) - 1)
        elif isinstance(contract, Option) or isinstance(contract, Future):
            multiplier = 100 if isinstance(contract, Option) else float(contract.multiplier)
            pnl = ((market_price / (average_cost / multiplier)) - 1)
    else:
        pnl = ((market_price / average_cost) - 1)

    pnl_percent = pnl * (-1) if position < 0 else pnl
    return pnl_percent * 100

def detect_duplicate_trade(portfoliomanager,trade):
    '''Function that checks for duplicate trades and returns True if one is found.'''
    q = QueryBuilder()
    q = q[(q['trade'] == str(trade))]
    existing_trade = portfoliomanager.portfolio_library.read(f"{portfoliomanager.account_id}",query_builder=q).data

    if not existing_trade.empty:
        print(f"Duplicate trade detected: {str(trade)}")
        return True