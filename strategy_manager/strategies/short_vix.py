import yfinance as yf
from ib_async import *
import pandas as pd
import numpy as np
import datetime, time, asyncio
from data_and_research import get_strategy_allocation_bounds, get_strategy_symbol
from broker.trademanager import TradeManager
from broker import connect_to_IB, disconnect_from_IB
from broker.functions import get_term_structure
from broker import connect_to_IB, disconnect_from_IB
from gui.log import add_log, start_event

PARAMS = {"VIX Threshold": 16.5, "Contango":True}

# TODO: # FINISH STRATEGY
        # Assign callbacks for order updates and code the functions in trade_manager which sends updates to strategy_manager
        # trade.fillEvent += self.trade_manager.on_fill
        # trade.statusEvent += self.trade_manager.on_status_change 
 
strategy = None

def manage_strategy(client_id, strategy_manager):
    try:
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Instantiate the Strategy class
        global strategy
        strategy = Strategy(client_id, strategy_manager)
        strategy.run()
    except Exception as e:
        # Handle exceptions
        print(f"Error in {strategy.strategy_symbol}: {e}")

    finally:
        # Clean up
        disconnect_from_IB(strategy.ib, strategy.strategy_symbol)
        loop.close()

def disconnect():
    strategy.disconnect()
    
class Strategy:
    def __init__(self, client_id, strategy_manager):
        self.client_id = client_id
        self.strategy_manager = strategy_manager
        self.filename = self.__class__.__module__ +".py"
        self.strategy_symbol = get_strategy_symbol(self.filename)
        self.SPY_yfTicker = "^GSPC"
        self.VIX_yfTicker = "^VIX"
        self.instrument_symbol = "VXM"

        # Get Data on Strategy Initialization
        self.ib = connect_to_IB(clientid=self.client_id, symbol=self.strategy_symbol)
        self.trade_manager = TradeManager(ib_client=self.ib,strategy_manager=self.strategy_manager)

        self.term_structure = get_term_structure(self.instrument_symbol,"VIX",ib=self.ib)
        print(self.term_structure)
        self.volatility_risk_premium = self.download_vix_and_spy_data()["VRP"].iloc[-1]
        self.is_contango = self.is_contango()
        
        # Position Management
        self.update_investment_status()
        self.update_invested_contract()
        #self.min_weight, self.target_weight, self.max_weight = 0.04, 0.07, 0.1
        self.target_weight, self.min_weight, self.max_weight = get_strategy_allocation_bounds(self.strategy_symbol)
        
    @staticmethod
    def check_investment_weight(self, symbol):
        """ Returns the investment weight for the given symbol. """
        try:
            # Sum up the investment value for all positions of the given symbol
            market_value = [pos.marketValue for pos in self.ib.portfolio() if pos.contract.symbol==symbol]
            market_value = market_value[0] if market_value else market_value
 
            if not market_value:
                return 0  # Symbol not found or has no value
 
            # Calculate and return the weight
            weight = (market_value / self.equity)
            return weight
 
        except Exception as e:
            print(f"Error calculating investment weight: {e}")
            return None  # or handle the error as appropriate

    def update_investment_status(self):
        """ Update the investment status of the strategy """
        self.equity = sum(float(entry.value) for entry in self.ib.accountSummary() if entry.tag == "EquityWithLoanValue")
        self.cash = sum(float(entry.value) for entry in self.ib.accountSummary() if entry.tag == "AvailableFunds")
        self.current_weight = self.check_investment_weight(self, symbol=self.instrument_symbol)
        self.invested = bool(self.current_weight)

    def update_invested_contract(self):
        """ Update the currently invested contract """
        if self.ib.portfolio():
            invested_contracts = [pos.contract for pos in self.ib.portfolio() if pos.contract.symbol == self.instrument_symbol]
            self.invested_contract = invested_contracts[0] if invested_contracts else None
            if self.invested_contract:
                self.ib.qualifyContracts(self.invested_contract)

    def download_vix_and_spy_data(self):
        """ Fetch historical data from Yahoo Finance """
        d = datetime.timedelta(days=120)
        end_date = datetime.date.today()
        start_date = end_date - d
        spx_df = yf.download("^GSPC", start=start_date)
        spx_df['Return'] = (spx_df['Close'] - spx_df['Close'].shift(1)) / spx_df['Close'].shift(1)
        spx_df = spx_df[['Close','Return']]
        spx_df['Realised Volatility'] = spx_df['Return'].rolling(21).std()*np.sqrt(252)*100
   
        vix_df = yf.download("^VIX", start=start_date)
        vix_df['VIX'] = vix_df['Close']
        vix_df = vix_df['VIX']
   
        self.vrp_df = spx_df.merge(vix_df, left_index=True, right_index=True, how='inner')
        self.vrp_df ['VRP'] = self.vrp_df ['VIX'].shift(21) - self.vrp_df ['Realised Volatility']
        #print("Latest Volatility Risk Premium",self.vrp_df.tail())
        return self.vrp_df
 
    def is_contango(self):
        """Returns True if VXM Futures trade in contango, False if in Backwardation"""
        try:
            self.is_contango = self.term_structure['LastPrice'].is_monotonic_increasing
        except:
            get_term_structure(self.instrument_symbol,self.VIX_yfTicker,yf=True,ib=self.ib)
            self.is_contango = self.term_structure['LastPrice'].is_monotonic_increasing
        return self.is_contango
 
    def calculate_number_of_contracts(self,allocated_amount, contract_price, contract_size):
        """
        Calculate the number of futures contracts to trade based on allocated amount.
 
        Args:
        allocated_amount (float): The dollar amount allocated for the futures contracts.
        contract_price (float): The price of a single futures contract.
        contract_size (float): The size of a single futures contract.
 
        Returns:
        int: The number of futures contracts to trade.
        """
        total_value = contract_price * contract_size
        number_of_contracts = allocated_amount // total_value
        return int(number_of_contracts)
 
    def choose_future_to_short(self):
        """
        Determine which VIX future to short based on the annualized yield and specific criteria.
 
        Working with:
        self.term_structure (DataFrame): DataFrame containing futures contract data.
 
        Returns:
        str: The contract to short.
        """

        # Filter out futures with prices below 16
        filtered_futures = self.term_structure[self.term_structure['LastPrice'] > 16]

        # Sort the filtered futures by AnnualizedYield in ascending order (most negative first)
        sorted_futures = filtered_futures.sort_values(by='AnnualizedYield')

        # Select the future with the highest (most negative) yield
        chosen_future = sorted_futures.iloc[0]['Contract'] if not sorted_futures.empty else None

        return chosen_future

    def check_conditions_and_trade(self):
        """ Check the trading conditions and execute trades """
        # Determine optimal Future to short
        symbol_to_short = self.choose_future_to_short()
        contract_to_short = self.ib.qualifyContracts(Future(localSymbol=symbol_to_short))[0]

        if not self.invested:
            if self.vrp_df["VRP"].iloc[-1] > 0:
                self.short_future(contract_to_short)
        else:
            # handle position management when invested
            current_contract = self.get_invested_contract()

            # when another contract has a higher expected yield, roll futures
            if current_contract != contract_to_short:
                self.roll_future(current_contract, contract_to_short)
            
            # Check for a natural roll
            dte = self.get_dte(current_contract)
            if dte <= 5:
                new_contract = self.get_next_contract(current_contract)
                if new_contract:
                    self.trade_manager.roll_future(current_contract, new_contract, orderRef=self.strategy_symbol)
            
            # check if we need to rebalance, because we are out of investment limits
            if self.min_weight < self.current_weight or self.current_weight > self.max_weight:
                allocated_amount = self.equity * self.target_weight
                contract_price = self.get_contract_price(current_contract)
                multiplier = int(current_contract.multiplier)
                target_quantity = self.calculate_number_of_contracts(allocated_amount,contract_price,multiplier)
                invested_quantity = [pos.position for pos in self.ib.portfolio() if pos.contract.localSymbol==current_contract.localSymbol][0]

                rebal_amount = target_quantity - abs(invested_quantity)

                if rebal_amount:
                    print(f"We need to change our positioning by {rebal_amount} contracts")
                    self.trade_manager.trade(current_contract,rebal_amount*-1)
    
    def run(self):
        add_log(f"{self.strategy_symbol} Thread Started")
        self.check_conditions_and_trade()
        # while start_event.is_set():
        #     add_log("Executing Strategy 2")
        #     time.sleep(4)
        #     add_log("S2: Listening to market data")
        #     time.sleep(4)
        #     add_log(f"S2: Weight:{self.current_weight}")
        #     add_log(f"S2: VXM Future in contango: {self.is_contango}")

    def disconnect(self):
        # Disconnect logic for the IB client
        disconnect_from_IB(ib=self.ib,symbol=self.strategy_symbol)

    def update_investment_status(self):
        """ Update the investment status of the strategy """
        self.equity = sum(float(entry.value) for entry in self.ib.accountSummary() if entry.tag == "EquityWithLoanValue")
        self.cash = sum(float(entry.value) for entry in self.ib.accountSummary() if entry.tag == "AvailableFunds")
        self.current_weight = self.check_investment_weight(self, symbol=self.instrument_symbol)
        self.invested = bool(self.current_weight)


    def update_invested_contract(self):
        """ Update the currently invested contract """
        if self.ib.portfolio():
            invested_contracts = [pos.contract for pos in self.ib.portfolio() if pos.contract.symbol == self.instrument_symbol]
            self.invested_contract = invested_contracts[0] if invested_contracts else None
            if self.invested_contract:
                self.ib.qualifyContracts(self.invested_contract)

    def get_next_contract(self, current_contract):
        """Find the next contract."""
        self.ib.qualifyContracts(current_contract)

        # Extract year and month from the current contract's lastTradeDateOrContractMonth
        expiration = current_contract.lastTradeDateOrContractMonth
        year, month = int(expiration[:4]), int(expiration[4:6])

        # Calculate the next month
        next_month = month + 1
        next_year = year
        if next_month > 12:
            next_month = 1
            next_year += 1

        next_month_str = f"{next_year}{next_month:02}"
        # Create the next contract
        next_contract = Future(symbol=current_contract.symbol, lastTradeDateOrContractMonth=next_month_str)
        self.ib.qualifyContracts(next_contract)

        return next_contract

    def get_dte(self,current_contract):
        today = datetime.datetime.now()         
        expiration_date = datetime.datetime.strptime(current_contract.lastTradeDateOrContractMonth, '%Y%m%d')
        dte = (expiration_date - today).days
        return dte

    def short_future(self, contract):
        """ Short a future contract """
        # self, contract, quantity, order_type='MKT', urgency='Patient', orderRef="", limit=None)
        allocated_amount = self.equity * self.target_weight
        if self.cash > allocated_amount:
            contract_price = self.get_contract_price(contract)
            multiplier = int(contract.multiplier)
            quantity = self.calculate_number_of_contracts(allocated_amount,contract_price,multiplier)
            print(f"Shorting {quantity} {contract.localSymbol}")
            self.trade_manager.trade(contract,quantity)
        else:
            add_log(f"Insufficient Cash to run strategy{self.strategy_symbol}")

    def get_invested_contract(self):
        """ Get the current future contract in the portfolio """
        if self.ib.portfolio():
            self.invested_contract = [pos.contract for pos in self.ib.portfolio() if pos.contract.symbol==self.instrument_symbol][0]
            self.ib.qualifyContracts(self.invested_contract)
            return self.invested_contract
        else:
            return None

    def get_contract_price(self,contract):
        market_data = self.ib.reqMktData(contract)
        self.ib.sleep(1)  # Wait for the data to be fetched
        last_price = market_data.last
        if last_price > 0:
            return last_price
        else:
            return market_data.bid

    def roll_future(self, current_contract, new_contract,orderRef=""):
        """
            Roll a futures contract by closing the current contract and opening a new one.

            :param current_contract: The current ib_insync.Contract to be closed.
            :param new_contract: The new ib_insync.Contract to be opened.
            :param orderRef: Reference identifier for the order.
        """
        if self.get_dte(current_contract) < self.get_dte(new_contract):
            self.trade_manager.roll_future(current_contract,new_contract,orderRef)
        else:
            add_log("Not allowed to roll future down the curve")

    def close_position(self, contract):
        """ Close the position in the given future contract """
        # Code for closing the position...

if __name__ == '__main__':
    print("main")