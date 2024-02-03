# ATS/broker/portfolio.py

import pandas as pd
from ib_insync import *
from gui.log import add_log
import datetime
from data_and_research import ac

class PortfolioManager:
    def __init__(self, ib_client: IB):
        self.ib = ib_client
        self.fx_cache = {}
        self.base = [entry.currency for entry in self.ib.accountSummary() if entry.tag == "EquityWithLoanValue"][0]

    def convert_marketValue_to_base(self,df):
        """returns a DataFrame with 'marketValue_base' column
        
        Args:
            df (pd.DataFrame): DataFrame containing the 'marketValue' column."""
        fx_rates = df['currency'].map(lambda c: self.get_fx_rate(c, self.base))

        if fx_rates.unique().size > 1:
            df['marketValue_base'] = df['marketValue'] / fx_rates
            df['fx_rate'] = fx_rates
        else:
            df['marketValue_base'] = df['marketValue']

        return df

    def get_fx_rate(self,currency, base_currency):
        """Retrieves the FX rate from a cached dictionary or live IB request.

        Args:
            currency (str): The currency to convert from.
            base_currency (str): The base currency to convert to."""

        if (currency, base_currency) not in self.fx_cache:
            if currency == base_currency:
                self.fx_cache[(currency, base_currency)] = 1.0
            else:
                fx_pair = Forex(base_currency+currency)
                self.ib.reqMarketDataType(4)  # Ensure market data type is set
                self.ib.qualifyContracts(fx_pair)
                price = self.ib.reqMktData(fx_pair, '', False, False)
                self.ib.sleep(0.2)  # Wait for data
                if type(price.marketPrice()) == int:
                    self.fx_cache[(currency, base_currency)] = price.marketPrice()
                else:
                    self.fx_cache[(currency, base_currency)] = price.close

        return self.fx_cache[(currency, base_currency)]

    def convert_to_base_currency(self,value: float, currency: str):
        currency = currency.upper()
        base =  [entry.currency for entry in self.ib.accountSummary() if entry.tag == "EquityWithLoanValue"][0]
        if base == currency:
            return value
        else:
            fx_pair = Forex(base+currency)

            market_data = self.ib.reqMktData(fx_pair, '', False, False)
            self.ib.sleep(1)

            if market_data.bid > 0:
                fx_spot = market_data.bid
            else:
                fx_spot = market_data.close
            
            base_value = value / fx_spot
            return base_value
    
    def calculate_pnl(self,row):
        asset_class = row['asset_class']
        if asset_class == 'STK' or asset_class == 'FUT':
            pnl = ((row.marketPrice/(row.averageCost)) -1)
            pnl = pnl *(-1) if row.position < 0 else pnl
        else: # case for options only (be more specific)
            if row.position < 0:
                pnl = ((row.marketPrice/(row.averageCost/100)) -1) * (-1)
            else:
                pnl = ( (row.marketPrice/ (row.averageCost/100)) -1)
        return pnl * 100

    def get_positions_from_ib(self):
        '''this function gets all portfolio positions in a dataframe format without strategy assignment'''
        total_equity =  sum(float(entry.value) for entry in self.ib.accountSummary() if entry.tag == "EquityWithLoanValue")
        portfolio_data = []

        for item in self.ib.portfolio():
            symbol = item.contract.symbol
            contractType = item.contract.secType

            if contractType == "OPT":
                right = "Call" if item.contract.right == "C" else "Put"
                asset_class = right + " " + str(item.contract.strike) + " " + item.contract.lastTradeDateOrContractMonth
                if item.position < 0:
                    pnl = ((item.marketPrice/(item.averageCost/100)) -1) * (-1)
                else:
                    pnl = ( (item.marketPrice/ (item.averageCost/100)) -1)
            elif contractType == "FUT":
                asset_class = item.contract.localSymbol + " " + item.contract.lastTradeDateOrContractMonth
                pnl = ((item.marketPrice/(item.averageCost/int(item.contract.multiplier))) -1)
                pnl = pnl *(-1) if item.position < 0 else pnl
            elif contractType == "STK":
                pnl = ((item.marketPrice/(item.averageCost)) -1)
                pnl = pnl *(-1) if item.position < 0 else pnl
                asset_class = contractType
            
            position_dict = {'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
                            'symbol': symbol,
                            'asset class': asset_class,
                            'position':item.position,
                            '% of nav':(item.marketValue/total_equity) * 100,
                            'averageCost': item.averageCost,
                            'marketPrice': item.marketPrice,
                            'pnl %': pnl * 100,
                            'strategy': '',
                            'contract': item.contract,
                            'trade': None,
                            'open_dt':datetime.date.today().isoformat(),
                            'marketValue': item.marketValue,
                            'unrealizedPNL': item.unrealizedPNL,
                            'currency':item.contract.currency,
                            'realizedPNL': item.realizedPNL,
                            'account': item.account}
            
            portfolio_data.append(position_dict)
                
        df = pd.DataFrame(portfolio_data)
        df = self.convert_marketValue_to_base(df)
        df['% of nav'] = df['% of nav'] / df.fx_rate
        return df
    
    def get_ib_positions_for_gui(self):
        df = self.get_positions_from_ib()
        df = df[['symbol','asset class','position','% of nav','currency','marketPrice','averageCost','pnl %','strategy']]
        return df
        
    def match_ib_positions_with_arcticdb(self):
        library = ac.get_library('portfolio')
        df_ac = library.read('positions').data
        latest_positions = df_ac.sort_values(by='timestamp').groupby(['symbol', 'strategy', 'asset class']).last().reset_index()
        df_ib = self.get_positions_from_ib()
        
