# ATS/broker/portfoliomanager.py

import pandas as pd
# import pandas_market_calendars as mcal
import math
from ib_async import *
import datetime
import yfinance as yf
from arcticdb import Arctic, QueryBuilder

from data_and_research import ac
from .utils import FXCache, create_position_dict, create_trade_entry ,calculate_pnl, detect_duplicate_trade

class PortfolioManager:
    def __init__(self, ib_client: IB,arctic = None):
        self.ib = ib_client
        self.fx_cache = FXCache(ib_client)
        self.base = [entry.currency for entry in self.ib.accountSummary() if entry.tag == "EquityWithLoanValue"][0]
        self.arctic = arctic if arctic else ac
        self.portfolio_library = self.arctic.get_library('portfolio', create_if_missing=True)
        self.pnl_library = self.arctic.get_library('pnl', create_if_missing=True)

        self.account_id = self.ib.managedAccounts()[0]
    
    def _create_strategy_entry_in_portfolio_lib_(self,strategy,symbol,quantity):
        '''Function for TESTING PURPOSES ONLY.'''
        self.total_equity =  sum(float(entry.value) for entry in self.ib.accountSummary() if entry.tag == "EquityWithLoanValue")

        item = [item for item in self.ib.portfolio() if item.contract.symbol == symbol][0]
        if not item:
            raise("Symbol not in portfolio. Choose a symbol from your portfolio for testing.")
        position = create_position_dict(self,item)
        df = pd.DataFrame([position])
        df.set_index('timestamp', inplace=True)
        df.loc[:,'strategy'] = strategy
        df.loc[:,'position'] = quantity

        df = self.fx_cache.convert_marketValue_to_base(df, self.base)
        df['% of nav'] = df['marketValue_base'] / self.total_equity * 100
        self.save_portfolio(df)

    def get_positions_from_ib(self):
        '''this function gets all portfolio positions in a dataframe format without strategy assignment'''
        self.total_equity =  sum(float(entry.value) for entry in self.ib.accountSummary() if entry.tag == "EquityWithLoanValue")
        portfolio_data = []

        for item in self.ib.portfolio():
            position = create_position_dict(self,item)
            portfolio_data.append(position)
        
        df = pd.DataFrame(portfolio_data)
        df.set_index('timestamp', inplace=True)

        df = self.fx_cache.convert_marketValue_to_base(df, self.base)
        df['% of nav'] = df['marketValue_base'] / self.total_equity * 100
        return df

    def get_ib_positions_for_gui(self):
        df = self.match_ib_positions_with_arcticdb()

        if df.empty: # simply return df in the case
            return df # no position are open
        
        df = df[['symbol','asset class','position','% of nav','currency','marketPrice','averageCost','pnl %','strategy']]
        # First, convert '% of nav' to numeric for sorting
        df['% of nav'] = pd.to_numeric(df['% of nav'], errors='coerce')

        # Then, sort by 'symbol' and within each 'symbol' group, sort by '% of nav' descending
        df_sorted = df.sort_values(by=['symbol', '% of nav'], ascending=[True, False])

        # If you also need to sort symbols by the max '% of nav' within each symbol group
        # you will need to create a temporary column for the max '% of nav' per symbol
        df_sorted['max_nav_per_symbol'] = df_sorted.groupby('symbol')['% of nav'].transform('max')

        # Now sort using this new column to get the symbols in order of their max '% of nav'
        df_final_sorted = df_sorted.sort_values(by=['max_nav_per_symbol', 'symbol', '% of nav'], ascending=[False, True, False])

        # Finally, you can drop the temporary column
        df_final_sorted = df_final_sorted.drop('max_nav_per_symbol', axis=1)

        return df_final_sorted

    def match_ib_positions_with_arcticdb(self):
        if self.account_id in self.portfolio_library.list_symbols():
            df_ac = self.load_portfolio_from_adb()
        else:
            df_ib = self.get_positions_from_ib()
            self.save_portfolio(df_ib)
            return df_ib

        df_ib = self.get_positions_from_ib()
        df_merged = pd.DataFrame()

        # Iterate through the positions obtained from Interactive Brokers
        for _, row in df_ib.iterrows():
            symbol = row['symbol']
            asset_class = row['asset class']

            strategy_entries_in_ac = df_ac[(df_ac['symbol'] == symbol) & (df_ac['asset class'] == asset_class)]
            
            if strategy_entries_in_ac.empty: # no database entry, add position
                # print(f"{asset_class}:{symbol} not in ArcticDB. Appending df_ib row to df_merged")
                df_merged = pd.concat([df_merged, pd.DataFrame([row])])
            else:
                strategy_entry_updated = self.update_and_aggregate_data(strategy_entries_in_ac, row)
                # print(f"{asset_class}:{symbol} in ArcticDB. Updated and aggregating data")
                df_merged = pd.concat([df_merged, strategy_entry_updated])
                
                if row['position'] - strategy_entry_updated.position.sum() != 0:
                    # Handle the residual and concat to df_merged
                    # print(f"{asset_class}:{symbol} IB position does not equal ArcticDB's Position")
                    residual = self.handle_residual(strategy_entries_in_ac, row)
                    df_merged = pd.concat([df_merged, residual])
 
        # Now, handle ArcticDB positions that aren't represented in the broker's data (e.g., strategies with net-zero positions)
        for _, row in df_ac.iterrows():
            symbol = row['symbol']
            asset_class = row['asset class']

            # Check if this position is not already accounted for in df_merged, then update market data
            if df_merged[(df_merged['symbol'] == symbol) & (df_merged['asset class'] == asset_class)].empty:
                # Update the market data for stale entries
                row = self.update_market_data_for_arcticdb_positions(row)

                # Otherwise, maintain the strategy-specific position, even if the broker doesn't report it
                df_merged = pd.concat([df_merged, pd.DataFrame([row])])

        self.save_portfolio(df_merged)
        self.save_account_pnl()
        
        return df_merged
    
    def update_and_aggregate_data(self, df_ac, row):
        '''Function to update ArcticDB dataframe entries with current market data.
        Will also combine same strategy symbol positions that resulted from discretionary/ manual trades.''' 
        self.total_equity = sum(float(entry.value) for entry in self.ib.accountSummary() if entry.tag == "EquityWithLoanValue")
        output_df = df_ac.copy()
        output_df.index = [row.name + pd.to_timedelta(i, unit='ns') for i in range(len(output_df))]

        # output_df.index = output_df.index + pd.to_timedelta(range(len(output_df)), unit='ns')
        # output_df['timestamp'] = row['timestamp'] if 'timestamp' in row else row.name
        # output_df['timestamp'] = output_df['timestamp'] + pd.to_timedelta(range(len(output_df)), unit='ns')
        output_df['marketPrice'] = row['marketPrice']

        # if position amounts in ArcticDB and the actual portfolio do not match for the same symbol 
        # and there is only one strategy entry, we simply combine them. Else we handle the residual later
        if (output_df['position'].sum() != row.position): 
                filter_mask = output_df['strategy'] == row['strategy']
                missing_amount = row.position - output_df['position'].sum()

                if len(output_df.loc[filter_mask, 'position'] > 0):
                    # Calculate the new average cost
                    total_cost = row.averageCost * row.position
                    total_cost_in_ac = (output_df['averageCost'] * output_df['position']).sum()
                    res_averageCost = (total_cost - total_cost_in_ac) / missing_amount

                    output_df.loc[filter_mask, 'averageCost'] = (output_df.loc[filter_mask, 'averageCost'] * output_df.loc[filter_mask, 'position'] 
                                                                + res_averageCost * missing_amount) / (output_df.loc[filter_mask, 'position'] + missing_amount)
                    output_df.loc[filter_mask, 'position'] += missing_amount 

        output_df['marketValue'] = output_df['marketPrice'] * output_df['position']
        output_df['marketValue_base'] = output_df['marketValue'] / row['fx_rate']
        output_df['% of nav'] = (output_df['marketValue_base'] / self.total_equity) * 100
        output_df['unrealizedPNL'] = output_df['marketPrice'] - output_df['averageCost']

        if len(output_df) == 1:
            output_df['pnl %'] = calculate_pnl(row.marketPrice, output_df.averageCost.item(), output_df.position.item(), row.contract)
        else:   # Handle multiple entries
            output_df['pnl %'] = output_df.apply(lambda x: calculate_pnl(x.marketPrice, x.averageCost, x.position, row.contract), axis=1)
            
        return output_df

    def update_market_data_for_arcticdb_positions(self, row):
        '''Function to update market data (marketPrice, marketValue, unrealizedPNL, etc.) for ArcticDB entries 
        that are not found in broker data.'''
        
        contract = eval(row['contract'])  # Convert the contract string back to the contract object
        self.ib.qualifyContracts(contract)

        fx_rate = self.fx_cache.get_fx_rate(contract.currency,self.base)
        row['fx_rate'] = fx_rate

        # Request live market data for the contract
        market_data = self.ib.reqMktData(contract, '', False, False)
        self.ib.sleep(1)  # Ensure sufficient time for data to populate
        
        # Update market-related fields
        row['marketPrice'] = market_data.marketPrice()
        row['marketValue'] = row['marketPrice'] * row['position']
        row['marketValue_base'] = row['marketValue'] / row['fx_rate']
        row['unrealizedPNL'] = (row['marketPrice'] - row['averageCost']) * row['position']
        row['timestamp'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # You can update other fields as necessary (e.g., `% of nav`)
        row['% of nav'] = (row['marketValue_base'] / self.total_equity) * 100
        return row

    def handle_residual(self,strategy_entries_in_ac, row):
        total_equity =  sum(float(entry.value) for entry in self.ib.accountSummary() if entry.tag == "EquityWithLoanValue")

        # Calculate the residual position
        total_position = row['position']
        assigned_position_sum = strategy_entries_in_ac['position'].sum()
        residual_position = total_position - assigned_position_sum

        # No residual to handle
        if residual_position == 0:
            return pd.DataFrame()

        # Calculate the weighted average cost for assigned positions
        weighted_avg_costs = (strategy_entries_in_ac['averageCost'] * strategy_entries_in_ac['position']).sum()
        total_weighted_cost = row['averageCost'] * total_position

        # Calculate the average cost for the residual position
        residual_avg_cost = (total_weighted_cost - weighted_avg_costs) / residual_position

        # Calculate updated market values for the residual
        market_price = row['marketPrice']
        residual_market_value = residual_position * market_price
        residual_percent_nav = ((residual_market_value / row.fx_rate) / total_equity) * 100
        pnl_percent = calculate_pnl(market_price,residual_avg_cost,residual_position,row.contract)

        # Prepare the residual row data
        residual_row = {
            'symbol': row['symbol'],
            'asset class': row['asset class'],
            'position': residual_position,
            'timestamp': datetime.datetime.now(),
            '% of nav': residual_percent_nav,
            'averageCost': residual_avg_cost,
            'marketPrice': market_price,
            'pnl %': pnl_percent,
            'strategy': '',  # This can be updated to assign a strategy later
            'contract': row['contract'],
            'trade': '',
            'trade_context': '',
            'open_dt': datetime.date.today().isoformat(),
            'close_dt': '',
            'deleted': False,
            'delete_dt': '',
            'marketValue': residual_market_value,
            'unrealizedPNL': (market_price - residual_avg_cost) * residual_position,
            'currency': row.currency,
            'realizedPNL': 0.0,  # Assuming no realized P&L for the residual; update as needed
            'account': row['account'],
            'marketValue_base': residual_market_value / row.fx_rate,
            'fx_rate': row.fx_rate}

        df = pd.DataFrame([residual_row])
        return df.set_index('timestamp', inplace=True)

    def load_portfolio_from_adb(self):
        '''Function that loads latest saved portfolio from ArcticDB'''
        today = datetime.date.today()
        df = self.portfolio_library.read(f"{self.account_id}",date_range=(today - pd.Timedelta(days=10), None)).data
        if df.empty:
            df = self.portfolio_library.read(f"{self.account_id}",row_range=(-5000,9999)).data

        # Slicing for only active positions
        df = df[df['deleted'] != True].copy()

        # Create a column of our index, to recreate the index later after grouping
        df['timestamp'] = df.index
        
        # Group by symbol, strategy and asset class to find their last updated value
        latest_portfolio = df.sort_index().groupby(['symbol', 'strategy', 'asset class']).last().reset_index()
        latest_portfolio.set_index('timestamp',drop=True, inplace=True)
        return latest_portfolio

    def save_portfolio(self, df_merged):
        '''Function that saves all positions in ArcticDB in portfolio/"account_id".'''
        if df_merged.empty:
            return
        df_merged = self.normalize_columns(df_merged)

        # Drop rows where the position is zero
        df_merged = df_merged[df_merged['position'] != 0]

        try:       
            if self.account_id in self.portfolio_library.list_symbols():
                print(f"Updating arcticdb entry {self.account_id} in library 'portfolio'")
                self.portfolio_library.update(f'{self.account_id}', df_merged,prune_previous_versions=True,upsert=True)
            else:
                print(f"Creating an arcticdb entry {self.account_id} in library 'portfolio'")
                self.portfolio_library.write(f'{self.account_id}',df_merged,prune_previous_versions = True)#,  validate_index=True)
        except Exception as e:
            print(f"Error occured while saving: {e}")

    def normalize_columns(self, df):
        df = df.copy()
        df['contract'] = df['contract'].astype(str)
        df['trade'] = df['trade'].astype(str)
        df['trade_context'] = df['trade_context'].astype(str)

        # Convert index to datetime
        df.index = pd.to_datetime(df.index, errors='coerce')

        # Create the 'timestamp' column if it doesn't exist
        if 'timestamp' not in df.columns:
            df['timestamp'] = df.index

        # Convert the 'timestamp' column to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

        # Compare index and 'timestamp' column, and keep the newer value
        df['timestamp'] = df.apply(lambda row: max(row.name, row['timestamp']) if pd.notnull(row['timestamp']) else row.name, axis=1)

        # Ensure all rows have a valid timestamp
        for idx, i in zip(df.index, range(0, len(df))):
            if pd.isna(df.at[idx, 'timestamp']):
                # If timestamp is NaT or missing, generate a unique timestamp
                df.at[idx, 'timestamp'] = pd.Timestamp.now() + pd.to_timedelta(i, unit='ns')

        # Set the 'timestamp' column as the index
        df.set_index('timestamp', inplace=True, drop=True)

        return df.sort_index()
    
    def save_account_pnl(self):
        """Saves the PnL (equity value) to the ArcticDB."""
        current_time = datetime.datetime.now().replace(second=0, microsecond=0)
        
        pnl_data = {'total_equity': self.total_equity,'account_id': self.account_id}
        pnl_df = pd.DataFrame([pnl_data], index=[current_time])
        try:
            # Append the new data to the 'pnl' library, creating it if it doesn't exist
            if self.account_id in self.pnl_library.list_symbols():
                self.pnl_library.append(self.account_id, pnl_df)
            else:
                self.pnl_library.write(self.account_id, pnl_df)
            print(f"Equity value saved to 'pnl' library for account {self.account_id}")
        except Exception as e:
            print(f"Error saving equity value to 'pnl' library: {e}")

    def delete_symbol(self,symbol, asset_class, position, strategy):
        q = QueryBuilder()
        q = q[(q['symbol']==symbol) & (q['asset class']==asset_class) &
              (q['strategy']==strategy) & (q['deleted']==False)]
        
        df = self.portfolio_library.read(f"{self.account_id}",query_builder=q).data

        df['deleted'] = True
        df['delete_dt'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Convert to string

        self.save_portfolio(df)

    ########################### PROCESSING NEW TRADES HERE ###########################
    # This part of the portfoliomanager handles incoming trades from the strategy manager queue 

    def process_new_trade(self, strategy_symbol, trade):
            '''Function that processes an ib_insync trade object and stores it in the ArcticDB'''
            # Create a Dataframe compatible with our ArcticDB data structure
            trade_df = create_trade_entry(self,strategy_symbol, trade)

            # Check for duplicate trades and exit function if True
            if detect_duplicate_trade(self,trade):
                return

            symbol = trade.contract.symbol
            asset_class = trade.contract.secType

            # Read the current portfolio data
            if self.account_id in self.portfolio_library.list_symbols():
                df_ac_active = self.load_portfolio_from_adb()
            else:
                df_ac_active = pd.DataFrame()

            existing_position = df_ac_active[(df_ac_active['symbol'] == symbol) & (df_ac_active['asset class'] == asset_class) 
                                            & (df_ac_active['strategy'] == strategy_symbol)]
    
            if existing_position.empty:
                # Simply append new position if it doesn't exist
                print(f"Processing a new trade: Saving {symbol} for strategy '{strategy_symbol}'")
                processed_trade_df = trade_df
                
            else:
                if len(existing_position) > 1:
                    print(existing_position)
                    print(f"Error: More than one entry of {asset_class}:{symbol} under '{strategy_symbol}'.")
                    return
                else:
                    if existing_position.position.item() + trade_df.position.item() == 0:
                        print(f"Processing a new trade: Closing {symbol} in strategy '{strategy_symbol}'")
                        self.close_position(existing_position, trade_df)
                        return
                    else:
                        # Aggregating new trade to an existing position that's not a close
                        print(f"Processing a new trade: Aggregating {symbol} to strategy '{strategy_symbol}'")
                        processed_trade_df = self.aggregate_positions(existing_position, trade_df)
                
            # Save the updated positions
            self.save_portfolio(processed_trade_df)
    
    def close_position(self,existing_position, trade_df):
        q = QueryBuilder()

        if isinstance(existing_position, pd.DataFrame): # when coming from process_new_trade()
            q = q[(q['symbol'] == existing_position.iloc[0]['symbol']) & \
                        (q['asset class'] == existing_position.iloc[0]['asset class']) & \
                        (q['strategy'] == existing_position.iloc[0]['strategy']) & \
                        (q['deleted'] == False)]
            
        elif isinstance(existing_position, dict): # when coming from the GUI
            q = q[(q['symbol'] == existing_position['symbol']) & \
                (q['asset class'] == existing_position['asset class']) & \
                (q['strategy'] == existing_position['strategy']) & \
                (q['deleted'] == False)]
        
        df = self.portfolio_library.read(f'{self.account_id}',query_builder=q).data

        # Select the latest matching entry to update the other columns
        df_to_update = df.copy()

        df_to_update['marketValue_base'] = 0.0
        df_to_update['% of nav'] = 0.0
        
        if not df_to_update['trade_context'].iloc[0]:
            trade_context = trade_df['trade_context'].iloc[0]
        elif isinstance(eval(df_to_update['trade_context'].iloc[0]), list):
            trade_context = eval(df_to_update['trade_context'].iloc[0])
            trade_context.append(trade_df['trade_context'].iloc[0])
        else:
            trade_context = [df_to_update['trade_context'].iloc[0], trade_df['trade_context'].iloc[0]]
        
        df_to_update['trade'] = trade_df['trade'].iloc[0]
        df_to_update['trade_context'] = str(trade_context)
        df_to_update['close_dt'] = datetime.date.today().isoformat()
        df_to_update['marketValue'] = 0.0
        df_to_update['unrealizedPNL'] = 0.0
        df_to_update['realizedPNL'] = (trade_df['averageCost'].iloc[0] - df_to_update['averageCost'].iloc[0]) * abs(df_to_update['position'].iloc[0])
        df_to_update['pnl %'] = df_to_update['realizedPNL'] / self.total_equity
        df_to_update['deleted'] = True
        df_to_update['delete_dt'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        self.save_portfolio(df_to_update)
        print(f"Closed position for {existing_position.iloc[0]['symbol']} {existing_position.iloc[0]['asset class']} with strategy {existing_position.iloc[0]['strategy']}")

    def aggregate_positions(self, existing_position, trade_df):
        '''Function to aggregate existing positions with new trade data'''
        df_merged = existing_position.copy()

        # Calculate new aggregated position
        total_position = existing_position['position'].iloc[0] + trade_df['position'].iloc[0]
        total_cost = (existing_position['averageCost'].iloc[0] * abs(existing_position['position'].iloc[0]) + 
                    trade_df['averageCost'].iloc[0] * abs(trade_df['position'].iloc[0]))

        new_average_cost = total_cost / ( abs(existing_position['position'].iloc[0]) + abs(trade_df['position'].iloc[0]) )

        df_merged['position'] = total_position
        df_merged['averageCost'] = new_average_cost

        # Update the rest of the fields based on new position
        df_merged['timestamp'] = datetime.datetime.now()
        df_merged.set_index('timestamp',drop=True, inplace=True)
        df_merged['marketPrice'] = trade_df['marketPrice'].iloc[0]
        df_merged['marketValue'] = df_merged['marketPrice'] * df_merged['position']
        df_merged['marketValue_base'] = df_merged['marketValue'] / trade_df['fx_rate'].iloc[0]
        df_merged['% of nav'] = (df_merged['marketValue_base'] / self.total_equity) * 100
        df_merged['unrealizedPNL'] = (df_merged['marketPrice'] - df_merged['averageCost']) * df_merged['position']

        # Handle trade context
        if not existing_position['trade_context'].iloc[0]:
            trade_context = trade_df['trade_context'].iloc[0]
        elif isinstance(eval(existing_position['trade_context'].iloc[0]), list):
            trade_context = eval(existing_position['trade_context'].iloc[0])
            trade_context.append(trade_df['trade_context'].iloc[0])  
        else:
            trade_context = [existing_position['trade_context'].iloc[0], trade_df['trade_context'].iloc[0]]
        
        df_merged['trade_context'] = str(trade_context)
        df_merged['trade'] = trade_df['trade'].iloc[0]
        return df_merged

