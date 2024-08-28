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
        
        # Create the index from the 'timestamp' field in each position dictionary
        dates = [pd.to_datetime(datetime.date.today().isoformat()) for _ in portfolio_data]
        df = pd.DataFrame(portfolio_data, index=dates)

        df = self.fx_cache.convert_marketValue_to_base(df, self.base)
        df['% of nav'] = df['marketValue_base'] / self.total_equity * 100
        return df

    def save_portfolio(self, df_merged):
        '''Function that saves all positions in ArcticDB in portfolio/"account_id".'''
        if df_merged.empty:
            return
        df_merged = self.normalize_columns(df_merged)

        # Drop rows where the position is zero
        df_merged = df_merged[df_merged['position'] != 0]

        # df_merged = df_merged.set_index('symbol',append=True)
        df_merged = df_merged.set_index('strategy',append=True)
        
        if self.account_id in self.portfolio_library.list_symbols():
            self.portfolio_library.update(f'{self.account_id}', df_merged,prune_previous_versions=True,upsert=True)
        else:
            print(f"Creating an arcticdb entry {self.account_id} in library 'portfolio'")
            self.portfolio_library.write(f'{self.account_id}',df_merged,prune_previous_versions = True)#,  validate_index=True)

    def normalize_columns(self, df):
        df = df.copy()
        df['contract'] = df['contract'].astype(str)
        df['trade'] = df['trade'].astype(str)
        df['trade_context'] = df['trade_context'].astype(str)
        return df
   