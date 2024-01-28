# ATS/broker/portfolio.py

import pandas as pd
from ib_insync import *
from gui.log import add_log
import datetime
from data_and_research import ac

class PortfolioManager:
    def __init__(self, ib_client: IB):
        self.ib = ib_client

    def convert_to_base_currency(self,value: float, currency: str):
        currency = currency.upper()
        base =  [entry.currency for entry in self.ib.accountSummary() if entry.tag == "EquityWithLoanValue"][0]
        fx_pair = Forex(base+currency)

        market_data = self.ib.reqMktData(fx_pair, '', False, False)
        self.ib.sleep(1)

        if market_data.bid > 0:
            fx_spot = market_data.bid
        else:
            fx_spot = market_data.close
        
        base_value = value / fx_spot
        return base_value

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
                pnl = ((item.marketPrice/(item.averageCost)) -1)
                pnl = pnl *(-1) if item.position < 0 else pnl
            elif contractType == "STK":
                pnl = ((item.marketPrice/(item.averageCost)) -1)
                pnl = pnl *(-1) if item.position < 0 else pnl
                asset_class = contractType
            
            position_dict = {'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
                            'symbol': symbol,
                            'asset class': asset_class,
                            'position':item.position,
                            '% of nav':item.marketValue/total_equity,
                            'averageCost': item.averageCost,
                            'marketPrice': item.marketPrice,
                            'pnl %': pnl,
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
        return df
    
    def get_ib_positions_for_gui(self):
        df = self.get_positions_from_ib()
        df = df[['symbol','asset class','position','% of nav','averageCost','marketPrice','pnl %','strategy']]
        return df
        
    def match_ib_positions_with_arcticdb(self):
        library = ac.get_library('portfolio')
        df_ac = library.read('positions').data
        latest_positions = df_ac.sort_values(by='timestamp').groupby(['symbol', 'strategy', 'asset class']).last().reset_index()
        df_ib = self.get_positions_from_ib()
        

    def fetch_portfolio(self):
        """
        Fetch the current portfolio and cash positions and combine them into a DataFrame.
        """
        # Fetch portfolio data
        portfolio_items = self.ib.portfolio()
        portfolio_data = [
            {
                "symbol": item.contract.symbol,
                "contractType": item.contract.secType,
                "position": item.position,
                "marketPrice": item.marketPrice,
                "marketValue": item.marketValue,
                "averageCost": item.averageCost,
                "unrealizedPNL": item.unrealizedPNL,
                "realizedPNL": item.realizedPNL,
                "conId": item.contract.conId,
                "lastTradeDate": item.contract.lastTradeDateOrContractMonth,
                "account": item.account
            }
            for item in portfolio_items
        ]
        portfolio_df = pd.DataFrame(portfolio_data)

        # Fetch cash positions
        cash_positions = [item for item in self.ib.accountSummary() if item.tag == 'CashBalance']
        cash_data = [
            {
                "symbol": item.currency,
                "contractType": "CASH",
                "position": float(item.value),
                "marketPrice": None,
                "marketValue": float(item.value),
                "averageCost": None,
                "unrealizedPNL": None,
                "realizedPNL": None,
                "conId": None,
                "lastTradeDate": None,
                "account": item.account
            }
            for item in cash_positions
        ]
        cash_df = pd.DataFrame(cash_data)

        # Combine portfolio and cash DataFrames
        combined_df = pd.concat([portfolio_df, cash_df], ignore_index=True)
        return combined_df
