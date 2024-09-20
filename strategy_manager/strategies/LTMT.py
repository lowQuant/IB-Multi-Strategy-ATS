# Long Term Market Timing Strategy (LTMT)

from ib_async import *
import asyncio, time, traceback, sys
from broker.trademanager import TradeManager
from broker import connect_to_IB, disconnect_from_IB
from data_and_research import get_strategy_allocation_bounds, get_strategy_symbol, fetch_strategy_params
from gui.log import add_log
import pandas as pd
import numpy as np
from datetime import datetime

PARAMS = {'symbol': 'ACWI','symbol_currency': 'USD','symbol_exchange': 'SMART',
          'ma_window': 10}

strategy = None

def manage_strategy(client_id, strategy_manager):
    try:
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Instantiate the Strategy class
        global strategy
        strategy = Strategy(client_id, strategy_manager)
        add_log(f"Thread Started [{strategy.strategy_symbol}]")
        strategy.run()

    except Exception as e:
            # Get the current exception information
            exc_type, exc_value, exc_traceback = sys.exc_info()
            
            # Extract the last frame (most recent call) from the traceback
            tb_frame = traceback.extract_tb(exc_traceback)[-1]
            filename = tb_frame.filename
            line_number = tb_frame.lineno
            
            # Print detailed error information
            print(f"Error in {filename}, line {line_number}: {str(e)}")
            print("Full traceback:")
            traceback.print_exc()

    finally: 
        # Clean up
        disconnect_from_IB(strategy.ib, strategy.strategy_symbol)
        loop.close()

def disconnect():
    if strategy:
        strategy.disconnect()

class Strategy:
    def __init__(self, client_id, strategy_manager):
        global PARAMS
        self.client_id = client_id
        self.strategy_manager = strategy_manager
        self.filename = self.__class__.__module__ +".py"
        self.strategy_symbol = get_strategy_symbol(self.filename)

        # Get Data on Strategy Initialization
        # Connect to Interactive Brokers
        self.ib = connect_to_IB(clientid=self.client_id, symbol=self.strategy_symbol)
        self.trade_manager = TradeManager(self.ib, self.strategy_manager)
        
        # Initialize strategy parameters
        self.target_weight, self.min_weight, self.max_weight = get_strategy_allocation_bounds(self.strategy_symbol)
        self.initialize_strategy()
        
    def initialize_strategy(self):
        """Initialize moving averages and signals"""
        self.params = fetch_strategy_params(self.strategy_symbol) if not None else PARAMS
        self.symbol = self.params['symbol']
        self.symbol_currency = self.params['symbol_currency']
        self.symbol_exchange = self.params['symbol_exchange']
        self.ma_window = int(self.params['ma_window'])
        
        # DataFrames to store historical prices and signals
        self.daily_data = pd.DataFrame()
        self.monthly_data = pd.DataFrame()
        
        # Fetch historical data
        self.fetch_historical_data()
        
        # Calculate Moving Averages
        self.calculate_moving_averages()
        
        # Generate Initial Signals
        self.generate_signals()
        
    def fetch_historical_data(self):
        """Fetch historical daily price data for the strategy symbol"""
        # Fetch historical daily data using IB API
        contract = Stock(self.symbol, 'SMART', 'USD')
        self.ib.reqMarketDataType(4)
        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr='10 Y',
            barSizeSetting='1 day',
            whatToShow='MIDPOINT',
            useRTH=True,
            formatDate=1
        )
        self.daily_data = util.df(bars)
        print(self.daily_data)
        self.daily_data['date'] = pd.to_datetime(self.daily_data['date'])
        self.daily_data.set_index('date', inplace=True)
        print(f"Fetched {len(self.daily_data)} historical daily data points for {self.strategy_symbol}")
        
    def calculate_moving_averages(self):
        """Calculate the Exponential Moving Average (EMA) on monthly data"""
        if not isinstance(self.daily_data.index, pd.DatetimeIndex):
            print("Converting index to DatetimeIndex")
            self.daily_data.index = pd.to_datetime(self.daily_data.index)
        
        # Ensure the index is sorted
        self.daily_data = self.daily_data.sort_index()
        
        # Resample to month end
        self.monthly_data = self.daily_data.resample('ME').last()
        
        # Calculate EMA
        self.monthly_data['EMA'] = self.monthly_data['close'].ewm(span=self.ma_window, adjust=False).mean()
        print(f"Calculated {self.ma_window}-month EMA for {self.strategy_symbol}")
        
    def generate_signals(self):
        """Generate buy/sell signals based on EMA crossover in monthly data"""
        self.monthly_data['Signal'] = 0
        # Generate Buy Signal: When Close > EMA
        self.monthly_data['Signal'] = np.where(self.monthly_data['close'] > self.monthly_data['EMA'], 1, 0)
        
        # Initialize Signal column in daily data
        self.daily_data['Signal'] = 0
        
        for i in range(len(self.daily_data)):
            current_date = self.daily_data.index[i]
            prev_month_end = current_date - pd.offsets.MonthEnd(1)
            try:
                signal = self.monthly_data.loc[prev_month_end, "Signal"]
                self.daily_data.loc[current_date, "Signal"] = signal
            except KeyError:
                # No signal for this date
                pass
        print(f"Mapped monthly signals to daily data for {self.strategy_symbol}")
        
    def update_investment_status(self):
        """Update the investment status of the strategy"""
        self.positions_df = self.strategy_manager.portfolio_manager.match_ib_positions_with_arcticdb()
        self.positions_df = self.positions_df[self.positions_df['symbol'] == self.strategy_symbol]
        # if self.positions_df.empty:
        #     print("Positions DataFrame is empty")
        #     self.current_position = 0
        self.current_position = self.positions_df['position'].iloc[-1] if not self.positions_df.empty else 0
        print(f"Current position for {self.strategy_symbol}: {self.current_position}")
        print(self.positions_df)

    def on_fill(self, trade, fill):
        """Handle fill event"""
        self.strategy_manager.message_queue.put({
            'type': 'fill',
            'strategy': self.strategy_symbol,
            'trade': trade,
            'fill': fill
        })
        add_log(f"Trade filled for {self.strategy_symbol}: {fill}")
        
    def on_status_change(self, trade):
        """Handle status change event"""
        self.strategy_manager.message_queue.put({
            'type': 'status_change',
            'strategy': self.strategy_symbol,
            'trade': trade,
            'status': trade.orderStatus.status,
            'info': f'Status Change message sent from {self.strategy_symbol}'
        })
        add_log(f"Trade status changed for {self.strategy_symbol}: {trade.orderStatus.status}")
        
    def run(self):
        """Main loop to execute trading strategy"""
        # Subscribe to real-time market data
        self.contract = Stock(self.symbol, 'SMART', 'USD')
        self.ib.reqMktData(self.contract, '', False, False)
        
        # Check if the strategy is already invested
        self.update_investment_status()
        
        last_run_date = None
        
        while True:
            current_date = datetime.now().date()
            
            # Run the strategy logic once per day
            if current_date != last_run_date:
                latest_signal = self.daily_data['Signal'].iloc[-1]
                
                if not self.current_position and latest_signal == 1:
                    # Buy Signal
                    trade = self.trade_manager.trade(self.contract, quantity=10,
                                             order_type='MKT',
                                             urgency='Patient', 
                                             useRth=True)
                    
                    add_log(f"Buy order placed for {self.strategy_symbol}")
                    
                    # Assign callbacks for order updates
                    trade.fillEvent += self.on_fill
                    trade.statusEvent += self.on_status_change
                    
                elif self.is_invested() and latest_signal == 0:
                    # Sell Signal
                    self.execute_trade('SELL', self.current_position)
                    add_log(f"Sell order placed for {self.strategy_symbol}")
                    
                elif self.is_invested() and self.check_rebalance_needed():
                    # Rebalance if needed
                    self.rebalance_position()
                    add_log(f"Rebalanced position for {self.strategy_symbol}")
                
                last_run_date = current_date
            
            # Sleep for a short time before checking again
            self.ib.sleep(60)  # Sleep for 1 minute


            
    def calculate_position_size(self):
        """Calculate the position size based on the strategy's target weight"""
        self.total_equity =  sum(float(entry.value) for entry in self.ib.accountSummary() if entry.tag == "EquityWithLoanValue")
        target_value = self.total_equity * self.target_weight

        
        current_price = self.ib.reqMktData(self.contract, '', False, False).marketPrice()
        quantity = target_value / current_price
        print(quantity)
        return quantity
    
    def execute_trade(self, action, quantity):
        """Execute a trade based on the action"""
        order_type = 'MKT'  # Market Order
        contract = Stock(self.symbol, 'SMART', 'USD')
        trade = self.trade_manager.trade(
            contract=contract,
            quantity=quantity if action == 'BUY' else -quantity,
            order_type=order_type,
            orderRef=self.strategy_symbol,
            urgency='Urgent',
            useRth=True
        )
        
        # Assign callbacks for order updates
        trade.fillEvent += self.on_fill
        trade.statusEvent += self.on_status_change
        
    def disconnect(self):
        """Disconnect logic for the IB client"""
        disconnect_from_IB(ib=self.ib, symbol=self.strategy_symbol)
        add_log(f"Disconnected from IB for {self.strategy_symbol}")