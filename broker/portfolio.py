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
        self.library = ac.get_library('portfolio', create_if_missing=True)

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
    
    def update_data(self,output_df,row):
        total_equity =  sum(float(entry.value) for entry in self.ib.accountSummary() if entry.tag == "EquityWithLoanValue")
        output_df = output_df.copy()
        output_df['timestamp'] = row['timestamp']
        output_df['marketPrice'] = row['marketPrice']
        output_df['marketValue_base'] = output_df['marketValue'] / row['fx_rate']
        output_df['pnl %'] = self.calculate_pnl(row.marketPrice,output_df.averageCost.item(),output_df.position.item(),row.contract)

        output_df['unrealizedPNL'] = output_df['marketPrice'] - output_df['averageCost']
        output_df['marketValue'] = (output_df['marketPrice'] * output_df['position']) 
        output_df['% of nav'] = (output_df['marketValue_base'] / total_equity) * 100
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
            'trade': None,
            'open_dt': datetime.date.today().isoformat(),
            'close_dt': None,
            'deleted': False,
            'marketValue': residual_market_value,
            'unrealizedPNL': (market_price - residual_avg_cost) * residual_position,
            'currency': row.currency,
            'realizedPNL': 0,  # Assuming no realized P&L for the residual; update as needed
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
                            'trade': None,
                            'open_dt':datetime.date.today().isoformat(),
                            'close_dt': None,
                            'deleted': False,
                            'marketValue': item.marketValue,
                            'unrealizedPNL': item.unrealizedPNL,
                            'currency':item.contract.currency,
                            'realizedPNL': item.realizedPNL,
                            'account': item.account,
                            'marketValue_base': None,
                            'fx_rate': None}
            
            portfolio_data.append(position_dict)
                
        df = pd.DataFrame(portfolio_data)

        # populates columns 'marketValue_base' and 'fx_rate'
        df = self.convert_marketValue_to_base(df)
        df['% of nav'] = df['% of nav'] / df.fx_rate
        return df
    
    def get_ib_positions_for_gui(self):
        df = self.match_ib_positions_with_arcticdb()
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

    def create_positions_table(self):
        df_ib = self.get_positions_from_ib()
        self.save_positions(df_ib)
        return df_ib

    def match_ib_positions_with_arcticdb(self):
        if 'positions' in self.library.list_symbols():
            df_ac = self.library.read('positions').data
        else:
            print("Msg from function 'match_ib_positions_with_arcticdb': No Symbol 'positions' in library 'portfolio'")
            df_ib = self.get_positions_from_ib()
            self.save_positions(df_ib)
            return df_ib

        latest_positions_in_ac = df_ac.sort_values(by='timestamp').groupby(['symbol', 'strategy', 'asset class']).last().reset_index()
        df_ib = self.get_positions_from_ib()

        df_merged = pd.DataFrame()

        # Iterate through the positions obtained from Interactive Brokers
        for index, row in df_ib.iterrows():
            symbol = row['symbol']
            asset_class = row['asset class']
            total_position = row['position']

            # Filter the ArcticDB DataFrame for entries with the same symbol and asset class
            strategy_entries_in_ac = latest_positions_in_ac[(latest_positions_in_ac['symbol'] == symbol) & (latest_positions_in_ac['asset class'] == asset_class)]
            sum_of_position_entries = strategy_entries_in_ac['position'].sum()

            if strategy_entries_in_ac.empty: # no database entry, add position
                df_merged = pd.concat([df_merged, pd.DataFrame([row])], ignore_index=True)

            elif len(strategy_entries_in_ac) == 1:
                if total_position == sum_of_position_entries:
                    # the positions match, we should only update fields relevant for marketdata in ac
                    strategy_entries_in_ac = self.update_data(strategy_entries_in_ac,row)
                    df_merged = pd.concat([df_merged, strategy_entries_in_ac], ignore_index=True)
                else:
                    #update marketdata relevant fields for the existing db entry
                    strategy_entries_in_ac = self.update_data(strategy_entries_in_ac,row)
                    df_merged = pd.concat([df_merged, strategy_entries_in_ac], ignore_index=True)
                    
                    # handle the residual and concat to df_merged
                    residual = self.handle_residual(strategy_entries_in_ac,row)
                    df_merged = pd.concat([df_merged, residual], ignore_index=True)

            elif len(strategy_entries_in_ac) > 1:
                if total_position == sum_of_position_entries:
                    strategy_entries_in_ac = self.update_data(strategy_entries_in_ac,row)
                    df_merged = pd.concat([df_merged, strategy_entries_in_ac], ignore_index=True)
                else:
                    #update marketdata relevant fields for the existing db entry
                    strategy_entries_in_ac = self.update_data(strategy_entries_in_ac,row)
                    df_merged = pd.concat([df_merged, strategy_entries_in_ac], ignore_index=True)
                    
                    # handle the residual and concat to df_merged
                    residual = self.handle_residual(strategy_entries_in_ac,row)
                    df_merged = pd.concat([df_merged, residual], ignore_index=True)

        self.save_positions(df_merged)
        return df_merged
    
    def save_positions(self, df_merged):
        df_merged = self.normalize_columns(df_merged)
        if 'positions' in self.library.list_symbols():
            self.library.append('positions', df_merged,prune_previous_versions=True,validate_index=False)
        else:
            print("Creating an arcticdb entry 'positions' in library 'portfolio'")
            self.library.write('positions',df_merged,prune_previous_versions = True,  validate_index=False)
                
    def normalize_columns(self, df):
        df['contract'] = df['contract'].astype(str)
        df['trade'] = df['trade'].astype(str)
        return df
