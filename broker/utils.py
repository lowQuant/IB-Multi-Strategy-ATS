# utils.py

import pandas as pd
import yfinance as yf
from ib_async import Forex
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
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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
            'deleted': str(False),
            'delete_dt': '',
            'marketValue': item.marketValue,
            'unrealizedPNL': item.unrealizedPNL,
            'currency':item.contract.currency,
            'realizedPNL': item.realizedPNL,
            'account': item.account,
            'marketValue_base': 0.0,
            'fx_rate': portfoliomanager.fx_cache.get_fx_rate(item.contract.currency, portfoliomanager.base)}

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

