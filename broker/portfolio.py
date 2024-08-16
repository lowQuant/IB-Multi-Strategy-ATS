# ATS/broker/portfolio.py

import pandas as pd
import math
from ib_async import *
from gui.log import add_log
import datetime
import yfinance as yf
from data_and_research import ac, initialize_db

class PortfolioManager:
    def __init__(self, ib_client: IB,arctic = None):
        self.ib = ib_client
        self.fx_cache = {}
        self.base = [entry.currency for entry in self.ib.accountSummary() if entry.tag == "EquityWithLoanValue"][0]
        # self.library = initialize_db('db').get_library('portfolio', create_if_missing=True) # ac.get_library('portfolio', create_if_missing=True)
        if arctic:
            self.portfolio_library = arctic.get_library('portfolio', create_if_missing=True)
            self.pnl_library = arctic.get_library('pnl', create_if_missing=True)
        else:
            self.portfolio_library = ac.get_library('portfolio', create_if_missing=True)
            self.pnl_library = ac.get_library('pnl', create_if_missing=True)
        self.account_id = self.ib.managedAccounts()[0]
        self.total_equity =  sum(float(entry.value) for entry in self.ib.accountSummary() if entry.tag == "EquityWithLoanValue")

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
                rate = self.ib.reqMktData(fx_pair, '', False, False)
                self.ib.sleep(0.2)  # Wait for data
                if type(rate.marketPrice()) == float and not math.isnan(rate.marketPrice()):
                    self.fx_cache[(currency, base_currency)] = rate.marketPrice()
                else:
                    if type(rate.close) == float:
                        if not math.isnan(rate.close):
                            self.fx_cache[(currency, base_currency)] = rate.close
                        else:
                            print("Using YF to get fx quote. Check IB connection for market data subscription. ")
                            ticker = f"{base_currency}{currency}=X"
                            try:
                                rate = yf.Ticker(ticker).info['ask']
                            except:
                                rate = 1.0
                            self.fx_cache[(currency, base_currency)] = rate
                            
        return self.fx_cache[(currency,base_currency)]

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
    
    def update_and_aggregate_data(self, strategy_entries_in_ac, row):
        '''Function to update ArcticDB dataframe entries with current market data.
        Will also combine same strategy symbol positions that resulted from discretionary/ manual trades.''' 
        
        self.total_equity = sum(float(entry.value) for entry in self.ib.accountSummary() if entry.tag == "EquityWithLoanValue")
        output_df = strategy_entries_in_ac.copy()
        output_df['timestamp'] = row['timestamp']
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
            output_df['pnl %'] = self.calculate_pnl(row.marketPrice, output_df.averageCost.item(), output_df.position.item(), row.contract)
        else:   # Handle multiple entries
            output_df['pnl %'] = output_df.apply(lambda x: self.calculate_pnl(x.marketPrice, x.averageCost, x.position, row.contract), axis=1)
            
        return output_df

    def calculate_pnl(self,market_price, average_cost, position, contract=None):
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
        pnl_percent = self.calculate_pnl(market_price,residual_avg_cost,residual_position,row.contract)

        # Prepare the residual row data
        residual_row = {
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
            'symbol': row['symbol'],
            'asset class': row['asset class'],
            'position': residual_position,
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

        # Return the residual row as a DataFrame
        return pd.DataFrame([residual_row])

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
                            'fx_rate': self.get_fx_rate(item.contract.currency, self.base)}
            
            portfolio_data.append(position_dict)
                
        df = pd.DataFrame(portfolio_data)

        # populates columns 'marketValue_base' and 'fx_rate'
        try:
            df = self.convert_marketValue_to_base(df)
            df['% of nav'] = df['% of nav'] / df.fx_rate
        except:
            pass
            #!TODO: think of better error handling
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
            df_ac = self.portfolio_library.read(f'{self.account_id}').data
            # Filter out deleted entries before comparing
            df_ac_active = df_ac[df_ac['deleted'] != True].copy()
            latest_positions_in_ac = df_ac_active.sort_values(by='timestamp').groupby(['symbol', 'strategy', 'asset class']).last().reset_index()
        else:
            df_ib = self.get_positions_from_ib()
            self.save_portfolio(df_ib)
            return df_ib

        df_ib = self.get_positions_from_ib()
        df_merged = pd.DataFrame()

        # Iterate through the positions obtained from Interactive Brokers
        for index, row in df_ib.iterrows():
            symbol = row['symbol']
            asset_class = row['asset class']
            total_position = row['position']

            # Filter the ArcticDB DataFrame for entries with the same symbol and asset class
            strategy_entries_in_ac = latest_positions_in_ac[(latest_positions_in_ac['symbol'] == symbol) & (latest_positions_in_ac['asset class'] == asset_class)]

            if strategy_entries_in_ac.empty: # no database entry, add position
                df_merged = pd.concat([df_merged, pd.DataFrame([row])], ignore_index=True)
            else:
                strategy_entry_updated = self.update_and_aggregate_data(strategy_entries_in_ac, row)
                df_merged = pd.concat([df_merged, strategy_entry_updated], ignore_index=True)

                if row['position'] - strategy_entry_updated.position.sum() != 0:
                    # Handle the residual and concat to df_merged
                    residual = self.handle_residual(strategy_entries_in_ac, row)
                    df_merged = pd.concat([df_merged, residual], ignore_index=True)
        
        self.save_portfolio(df_merged)
        self.save_account_pnl()
        return df_merged
    
    def save_portfolio(self, df_merged):
        '''Function that saves all positions in ArcticDB in portfolio/"account_id".'''
        if df_merged.empty:
            return
        df_merged = self.normalize_columns(df_merged)
        if self.account_id in self.portfolio_library.list_symbols():
            self.portfolio_library.append(f'{self.account_id}', df_merged,prune_previous_versions=True,validate_index=True)
        else:
            print(f"Creating an arcticdb entry {self.account_id} in library 'portfolio'")
            self.portfolio_library.write(f'{self.account_id}',df_merged,prune_previous_versions = True,  validate_index=True)

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

    def process_new_trade(self, strategy_symbol, trade):
        '''Function that processes an ib_insync trade object and stores it in the ArcticDB'''
        print(f"process_new_trade: func called.")
        # Create a Dataframe compatible with our ArcticDB data structure
        trade_df = self.create_trade_entry(strategy_symbol, trade)
        print(trade_df)
        # Check if this is a new position or an update to an existing position
        symbol = trade.contract.symbol
        asset_class = trade.contract.secType

        # Read the current portfolio data
        if self.account_id in self.portfolio_library.list_symbols():
            df_ac = self.portfolio_library.read(f'{self.account_id}').data
            df_ac_active = df_ac[df_ac['deleted'] != True].copy()
        else:
            df_ac_active = pd.DataFrame()

        # Check for duplicate trades
        if str(trade) in df_ac['trade'].values:
            print(f"Duplicate trade detected: {str(trade)}")
            return

        # Filter for the same symbol and asset class in the active portfolio
        df_ac_active = df_ac_active[df_ac_active['deleted'] != True].copy()
        # df_ac_active = df_ac_active.sort_values(by='timestamp').groupby(['symbol', 'strategy', 'asset class','position']).last().reset_index()
        df_ac_active = df_ac_active.sort_values(by='timestamp').groupby(['symbol', 'strategy', 'asset class']).last().reset_index()
        existing_position = df_ac_active[(df_ac_active['symbol'] == symbol) & (df_ac_active['asset class'] == asset_class) 
                                        & (df_ac_active['strategy'] == strategy_symbol)]

        if existing_position.empty:
            # Simply append new position if it doesn't exist
            print(f"process_new_trade: Saving new position in ArcticDB under symbol {symbol}")
            df_merged = pd.concat([df_ac_active, trade_df], ignore_index=True)
        else:
            if len(existing_position) > 1:
                print(existing_position)
                print(f"Error: More than one entry of {asset_class}:{symbol} under {strategy_symbol}.")
                return
            else:
                if existing_position.position.item() + trade_df.position.item() == 0:
                    self.close_position(existing_position, trade_df)
                    return
                else:
                    # Update existing position or close position
                    # !TODO: Continue here
                    print(f"process_new_trade: Aggregating trade under symbol {symbol}")
                    df_merged = self.aggregate_positions(existing_position, trade_df)
            
        # Save the updated positions
        self.save_portfolio(df_merged.reset_index(drop=True))

    def create_trade_entry(self, strategy_symbol,trade):
        '''Function to create a Dataframe from ib_insync's trade object
           for further processing in our arcticDB.'''
        fx_rate = self.get_fx_rate(trade.contract.currency,self.base)
        cost = trade.orderStatus.avgFillPrice
        qty =  trade.order.totalQuantity *(-1) if trade.order.action == 'SELL' else trade.order.totalQuantity 
        value = cost*qty
        value_base = value / fx_rate
        
        try:
            trade_dict = {'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
            'symbol': trade.contract.symbol,
            'asset class': trade.contract.secType,
            'position': qty,
            '% of nav': value_base / self.total_equity  , # to be calculated
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
        return trade_df

    def close_position(self,existing_position, trade_df):

        df = self.portfolio_library.read(f'{self.account_id}').data

        if isinstance(existing_position, pd.DataFrame):
            filter_condition = (df['symbol'] == existing_position.iloc[0]['symbol']) & \
                        (df['asset class'] == existing_position.iloc[0]['asset class']) & \
                        (df['position'] == existing_position.iloc[0]['position']) & \
                        (df['strategy'] == existing_position.iloc[0]['strategy']) & \
                        (df['deleted'] == False)
            
        elif isinstance(existing_position, dict):
            filter_condition = (df['symbol'] == existing_position['symbol']) & \
                        (df['asset class'] == existing_position['asset class']) & \
                        (df['position'] == existing_position['position']) & \
                        (df['strategy'] == existing_position['strategy']) & \
                        (df['deleted'] == False)

        # Delete the trade entries among all row entries
        df.loc[filter_condition, 'deleted'] = True
        df.loc[filter_condition, 'delete_dt'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Convert to string

        # Select the latest matching entry to update the other columns
        df_to_update = df[filter_condition][-1:].copy()

        df_to_update['timestamp'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        df_to_update['marketValue_base'] = 0.0
        df_to_update['% of nav'] = 0.0
        df_to_update['pnl %'] = 0.0

        if not df_to_update['trade_context'].iloc[0]:
            trade_context = trade_df['trade_context'].iloc[0]
        elif isinstance(eval(df_to_update['trade_context'].iloc[0]), str):
            trade_context = [df_to_update['trade_context'].iloc[0], trade_df['trade_context'].iloc[0]]
        else:
            trade_context = eval(df_to_update['trade_context'].iloc[0])
            trade_context.append(trade_df['trade_context'].iloc[0])
        
        df_to_update['trade'] = trade_df['trade'].iloc[0]
        df_to_update['trade_context'] = trade_context
        df_to_update['close_dt'] = datetime.date.today().isoformat()
        df_to_update['marketValue'] = 0.0
        df_to_update['unrealizedPNL'] = 0.0
        df_to_update['realizedPNL'] = (trade_df['averageCost'].iloc[0] - df_to_update['averageCost'].iloc[0]) * abs(df_to_update['position'].iloc[0])
        df_to_update['deleted'] = True
        df_to_update['delete_dt'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

         # Append the updated closing entry to the DataFrame
        df = pd.concat([df, df_to_update], ignore_index=True)

        # Save the updated DataFrame back to ArcticDB
        df = self.normalize_columns(df)
        self.portfolio_library.write(f'{self.account_id}', df, prune_previous_versions=True)
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
        df_merged['timestamp'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        df_merged['marketPrice'] = trade_df['marketPrice'].iloc[0]
        df_merged['marketValue'] = df_merged['marketPrice'] * df_merged['position']
        df_merged['marketValue_base'] = df_merged['marketValue'] / trade_df['fx_rate'].iloc[0]
        df_merged['% of nav'] = (df_merged['marketValue_base'] / self.total_equity) * 100
        df_merged['unrealizedPNL'] = (df_merged['marketPrice'] - df_merged['averageCost']) * df_merged['position']

        # Handle trade context
        if not existing_position['trade_context'].iloc[0]:
            trade_context = trade_df['trade_context'].iloc[0]
        elif isinstance(existing_position['trade_context'].iloc[0], str):
            trade_context = [existing_position['trade_context'].iloc[0], trade_df['trade_context'].iloc[0]]
        else:
            trade_context = eval(existing_position['trade_context'].iloc[0])
            trade_context.append(trade_df['trade_context'].iloc[0])
        
        df_merged['trade_context'] = str(trade_context)
        df_merged['trade'] = trade_df['trade'].iloc[0]
        
        return df_merged
    
    def save_position(self,trade_df: pd.DataFrame = None, trade_dict: dict = None, target_row_dict: dict = None):
        pass

    def save_existing_position_to_strategy_portfolio(self,df,strategy):
        '''Function that saves position to portfolio/"account_id"_"strategy symbol"'''
        if strategy:
            df = self.normalize_columns(df)

            if f"{self.account_id}_{strategy}" in self.portfolio_library.list_symbols():
                self.portfolio_library.append(f'{self.account_id}_{strategy}', df,prune_previous_versions=True,validate_index=True)
            else:
                print(f"Creating an arcticdb entry {self.account_id}_{strategy} in library 'portfolio'")
                self.portfolio_library.write(f'{self.account_id}_{strategy}',df,prune_previous_versions = True,  validate_index=True)

    def delete_symbol(self,symbol, asset_class, position, strategy):
        ''' A function that deletes an ArcticDB entry based on provided params:
            -symbol, asset_class, position & strategy'''
        
        df = self.portfolio_library.read(f'{self.account_id}').data

        # Filter for matching entries that have not been previously marked as deleted
        filter_condition = (df['symbol'] == symbol) & \
                        (df['asset class'] == asset_class) & \
                        (df['position'] == float(position)) & \
                        (df['strategy'] == strategy) & \
                        (df['deleted'] == False)

        # Mark the filtered entries as deleted and add the current timestamp
        df.loc[filter_condition, 'deleted'] = True
        df.loc[filter_condition, 'delete_dt'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Convert to string

        # Save the updated DataFrame back to ArcticDB
        df = self.normalize_columns(df)
        self.portfolio_library.write(f'{self.account_id}', df, prune_previous_versions=True)

        print(f"Deleted positions for {symbol} {asset_class} with position {position}")

    def normalize_columns(self, df):
        df = df.copy()
        df['contract'] = df['contract'].astype(str)
        df['trade'] = df['trade'].astype(str)
        return df
    
    def delete_symbol_from_portfolio_lib(self,symbol):
        self.portfolio_library.delete(symbol)
