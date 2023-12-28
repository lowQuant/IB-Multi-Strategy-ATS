# ATS/broker/portfolio.py

import pandas as pd
from ib_insync import *
from gui.log import add_log

class PortfolioManager:
    def __init__(self, ib_client: IB):
        self.ib = ib_client

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
