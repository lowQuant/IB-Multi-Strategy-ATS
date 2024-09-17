# Long Term Market Timing Strategy (LTMT)

from ib_async import *
import asyncio, time
from broker.trademanager import TradeManager
from broker import connect_to_IB, disconnect_from_IB
from data_and_research import get_strategy_allocation_bounds, get_strategy_symbol
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
        # Handle exceptions
        print(f"Error when instantiating: {e}")

    finally:
        # Clean up
        disconnect_from_IB(strategy.ib, strategy.strategy_symbol)
        loop.close()

def disconnect():
    if strategy:
        strategy.disconnect()

class Strategy:
    def __init__(self, client_id, strategy_manager):
        self.client_id = client_id
        self.strategy_manager = strategy_manager
        self.filename = self.__class__.__module__ + ".py"
        self.strategy_symbol = get_strategy_symbol(self.filename)
        
        # Connect to Interactive Brokers
        self.ib = connect_to_IB(clientid=self.client_id, symbol=self.strategy_symbol)
        self.trade_manager = TradeManager(self.ib, self.strategy_manager)
        
        # Initialize strategy parameters
        self.initialize_strategy()
        
    def initialize_strategy(self):
        """Initialize moving averages and signals"""
        # Parameters for Moving Averages
        self.ma_window = PARAMS['ma_window']  # 10-month EMA
        
        # DataFrames to store historical prices and signals
        self.daily_data = pd.DataFrame()
        self.monthly_data = pd.DataFrame()
        
        # Fetch historical data
        self.fetch_historical_data()
        
        # Calculate Moving Averages
        self.calculate_moving_averages()
        
        # Generate Initial Signals
        self.generate_signals()
        
        # Map monthly signals to daily data
        self.map_signals_to_daily()
        
    def fetch_historical_data(self):
        """Fetch historical daily price data for the strategy symbol"""
        # Fetch historical daily data using IB API
        contract = Stock(self.strategy_symbol, 'SMART', 'USD')
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
        self.daily_data.set_index('date', inplace=True)
        add_log(f"Fetched {len(self.daily_data)} historical daily data points for {self.strategy_symbol}")
        
    def calculate_moving_averages(self):
        """Calculate the Exponential Moving Average (EMA) on monthly data"""
        # Resample daily data to month end
        self.monthly_data = self.daily_data.resample('ME').last()
        
        # Calculate EMA
        self.monthly_data['EMA'] = self.monthly_data['close'].ewm(span=self.ma_window, adjust=False).mean()
        add_log(f"Calculated {self.ma_window}-month EMA for {self.strategy_symbol}")
        
    def generate_signals(self):
        """Generate buy/sell signals based on EMA crossover in monthly data"""
        self.monthly_data['Signal'] = 0
        # Generate Buy Signal: When Close > EMA
        self.monthly_data['Signal'] = np.where(self.monthly_data['close'] > self.monthly_data['EMA'], 1, 0)
        # Calculate Position Changes
        self.monthly_data['Position'] = self.monthly_data['Signal'].diff()
        add_log(f"Generated buy/sell signals for {self.strategy_symbol}")
        
    def map_signals_to_daily(self):
        """Map monthly signals to daily data"""
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
        add_log(f"Mapped monthly signals to daily data for {self.strategy_symbol}")
        
    def update_investment_status(self):
        """Update the investment status of the strategy"""
        # TODO: Integrate with Portfolio Manager if available
        pass
    
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
        contract = Stock(self.strategy_symbol, 'SMART', 'USD')
        self.ib.reqMktData(contract, '', False, False)
        
        # Initialize last signal to prevent duplicate orders
        self.last_signal = 0
        
        add_log(f"Starting trading loop for {self.strategy_symbol}")
        
        while True:
            # Get current date
            current_datetime = datetime.now()
            current_date = current_datetime.date()
            
            # Check if today is the first trading day of the month
            if current_date.day == 1:
                add_log(f"First day of the month detected for {self.strategy_symbol}")
                # Fetch the latest month's data
                self.fetch_latest_month()
                # Generate and execute signals
                self.process_signals()
            
            # Sleep until the next day
            time.sleep(86400)  # Sleep for one day
                    
    def fetch_latest_month(self):
        """Fetch the latest month's closing price and update moving averages"""
        contract = Stock(self.strategy_symbol, 'SMART', 'USD')
        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr='1 M',
            barSizeSetting='1 day',
            whatToShow='MIDPOINT',
            useRTH=True,
            formatDate=1
        )
        latest_data = util.df(bars)
        if not latest_data.empty:
            latest_data.set_index('date', inplace=True)
            # Append to daily data
            self.daily_data = pd.concat([self.daily_data, latest_data])
            # Resample to month end and recalculate EMA
            self.calculate_moving_averages()
            # Regenerate signals
            self.generate_signals()
            # Remap signals to daily data
            self.map_signals_to_daily()
            add_log(f"Fetched and updated latest month data for {self.strategy_symbol}")
        
    def process_signals(self):
        """Process the latest signal and execute trades accordingly"""
        if len(self.daily_data) < self.ma_window:
            add_log(f"Not enough data to generate signals for {self.strategy_symbol}")
            return
        
        latest_signal = self.daily_data['Signal'].iloc[-1]
        prev_signal = self.daily_data['Signal'].iloc[-2] if len(self.daily_data) >=2 else 0
        position_change = latest_signal - prev_signal
        
        if position_change == 1 and self.last_signal != 1:
            # Buy Signal
            self.execute_trade('BUY', 1)
            self.last_signal = 1
            add_log(f"Buy signal generated for {self.strategy_symbol} on {self.daily_data.index[-1].date()}")
            
        elif position_change == -1 and self.last_signal != -1:
            # Sell Signal
            self.execute_trade('SELL', 1)
            self.last_signal = -1
            add_log(f"Sell signal generated for {self.strategy_symbol} on {self.daily_data.index[-1].date()}")
        
    def execute_trade(self, action, quantity):
        """Execute a trade based on the action"""
        order_type = 'MKT'  # Market Order
        contract = Stock(self.strategy_symbol, 'SMART', 'USD')
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