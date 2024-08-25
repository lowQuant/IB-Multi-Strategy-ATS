# ATS/broker/portfoliomanager.py

import pandas as pd
import math
from ib_async import *
import datetime
import yfinance as yf

from data_and_research import ac
from .utils import FXCache, create_position_dict

class PortfolioManager:
    def __init__(self, ib_client: IB,arctic = None):
        self.ib = ib_client
        self.fx_cache = FXCache(ib_client)
        self.base = [entry.currency for entry in self.ib.accountSummary() if entry.tag == "EquityWithLoanValue"][0]
        if arctic:
            self.portfolio_library = arctic.get_library('portfolio', create_if_missing=True)
            self.pnl_library = arctic.get_library('pnl', create_if_missing=True)
        else:
            self.portfolio_library = ac.get_library('portfolio', create_if_missing=True)
            self.pnl_library = ac.get_library('pnl', create_if_missing=True)
        self.account_id = self.ib.managedAccounts()[0]

    def get_positions_from_ib(self):
        '''this function gets all portfolio positions in a dataframe format without strategy assignment'''
        self.total_equity =  sum(float(entry.value) for entry in self.ib.accountSummary() if entry.tag == "EquityWithLoanValue")
        portfolio_data = []

        for item in self.ib.portfolio():
            position = create_position_dict(self,item)
            portfolio_data.append(position)
        
        df = pd.DataFrame(portfolio_data)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True, drop=True)

        df = self.fx_cache.convert_marketValue_to_base(df, self.base)
        df['% of nav'] = df['marketValue_base'] / self.total_equity * 100
        return df
   