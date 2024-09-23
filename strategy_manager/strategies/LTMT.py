# Long Term Market Timing Strategy (LTMT)

from ib_async import *
import asyncio, time, traceback, sys, math
from broker.trademanager import TradeManager
from broker import connect_to_IB, disconnect_from_IB
from data_and_research import get_strategy_allocation_bounds, get_strategy_symbol, fetch_strategy_params
from gui.log import add_log
import pandas as pd
import numpy as np
from datetime import datetime
import yfinance as yf
PARAMS = {'symbol': 'ACWI','symbol_currency': 'USD','symbol_exchange': 'SMART',
          'yfinance_symbol': 'IUSQ.DE',
          'ma_window': 10}

strategy = None

def manage_strategy(client_id, strategy_manager, strategy_loops):
    try:
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Instantiate the Strategy class
        global strategy
        strategy = Strategy(client_id, strategy_manager)
        strategy.start()
        add_log(f"Thread Started [{strategy.strategy_symbol}]")

        # Store the loop in the shared dictionary for later reference
        strategy_loops[client_id] = loop

        loop.run_forever()

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
        disconnect()
        loop.close()
        # Remove the loop reference from the shared dictionary
        del strategy_loops[client_id]

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
        self.yfinance_symbol = self.params['yfinance_symbol']

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
        try:
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
            self.daily_data['date'] = pd.to_datetime(self.daily_data['date'])
            self.daily_data.set_index('date', inplace=True)
            print(f"Fetched {len(self.daily_data)} historical daily data points for {self.strategy_symbol}")
        except Exception as e:
            print(f"Error fetching historical data for {self.strategy_symbol}: {e}")
            print("Trying to fetch historical data with yfinance")
            self.daily_data = yf.download(self.yfinance_symbol, period="max", interval="1d")
            self.daily_data.rename(columns={'Close':'close'}, inplace=True)

    def calculate_moving_averages(self):
        """Calculate the Exponential Moving Average (EMA) on monthly data"""
        print(f"Calculating {self.ma_window}-month EMA for {self.strategy_symbol}")
        if not isinstance(self.daily_data.index, pd.DatetimeIndex):
            print("Converting index to DatetimeIndex")
            self.daily_data.index = pd.to_datetime(self.daily_data.index)

        # Ensure the index is sorted
        self.daily_data = self.daily_data.sort_index()
        
        # Resample to month end
        try:
            self.monthly_data = self.daily_data.resample('ME').last()
        except Exception as e:
            self.monthly_data = self.daily_data.resample('M').last()
        
        # Calculate EMA
        self.monthly_data['EMA'] = self.monthly_data['close'].ewm(span=self.ma_window, adjust=False).mean()
        
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

        self.current_position = int(self.positions_df['position'].iloc[-1]) if not self.positions_df.empty else 0
        print(f"Current position for {self.strategy_symbol}: {self.current_position}")
        if self.current_position:   
            self.invested_value = self.positions_df['marketValue_base'].iloc[-1]
            self.current_weight = self.positions_df['% of nav'].iloc[-1]

    def on_fill(self, trade, fill):
        """Handle fill event"""
        self.strategy_manager.message_queue.put({
            'type': 'fill',
            'strategy': self.strategy_symbol,
            'trade': trade,
            'fill': fill
        })
        
    def on_status_change(self, trade):
        """Handle status change event"""
        self.strategy_manager.message_queue.put({
            'type': 'status_change',
            'strategy': self.strategy_symbol,
            'trade': trade,
            'status': trade.orderStatus.status,
            'info': f'Status Change message sent from {self.strategy_symbol}'
        })
        
    async def run(self):
        """Main loop to execute trading strategy"""
        # Subscribe to real-time market data
        self.contract = Stock(self.symbol, self.symbol_exchange, self.symbol_currency)
        self.ib.reqMktData(self.contract, '', False, False)
        
        # Check if the strategy is already invested
        self.update_investment_status()
        orders = [o for o in self.strategy_manager.get_open_orders()]
        
        last_run_date = None
        
        while True:
            print(self.daily_data)
            latest_signal = self.daily_data['Signal'].iloc[-1]
            
            if not self.current_position and latest_signal == 1:
                if not self.strategy_symbol in [o.orderRef for o in orders]:
                    print(f"Opening position for {self.strategy_symbol}")

                    trade = self.place_order(self.contract,qty=self.calculate_position_size(),
                                             ordertype='MKT', urgency='Patient',
                                             orderRef= self.strategy_symbol)
                else:
                     print(f"Order already exists for {self.strategy_symbol}")

            elif self.is_invested() and latest_signal == 0:
                print(f"Closing position for {self.strategy_symbol}")

                # Sell Signal
                trade = self.place_order(self.contract, qty=self.current_position*-1,
                                         ordertype='MKT', urgency='Patient',
                                         orderRef= self.strategy_symbol)

            elif self.is_invested() and self.check_rebalance_needed():
                # Rebalance if needed
                trade = self.rebalance_position()
                add_log(f"Rebalancing position for {self.strategy_symbol}")
            
            # Sleep until the next day
            print(f"Sleeping until one day")
            await asyncio.sleep(86400)  # Sleep for one day

    def start(self):
        """Start the strategy"""
        asyncio.ensure_future(self.run())
    
    def place_order(self, con, qty, ordertype, algo = True, urgency='Patient', orderRef = "", limit = None, useRth=True):
        trade = self.trade_manager.trade(con,quantity=qty,order_type=ordertype,urgency=urgency,orderRef=orderRef,useRth=useRth)
        # Assign callbacks for order updates
        trade.fillEvent += self.on_fill
        trade.statusEvent += self.on_status_change
        return trade

    def check_rebalance_needed(self):
        """Check if a rebalance is needed based on the strategy's target weight"""
        return True if self.current_weight > self.max_weight or self.current_weight < self.min_weight else False

    def calculate_position_size(self):
        """Calculate the position size based on the strategy's target weight"""
        self.total_equity =  sum(float(entry.value) for entry in self.ib.accountSummary() if entry.tag == "EquityWithLoanValue")
        target_value = self.total_equity * float(self.target_weight)

        
        current_price = self.ib.reqMktData(self.contract, '', False, False).marketPrice()
        
        if math.isnan(current_price):
            current_price = self.daily_data['close'].iloc[-1]
        print("Current Price", current_price)

        quantity = math.floor(target_value / current_price)
        print(f"Calculated quantity: {quantity}")
        return quantity

    def rebalance_position(self):
        """Rebalance the position based on the strategy's target weight"""
        target_quantity = self.calculate_position_size()
        if target_quantity > self.current_position:
            # Buy       
            trade = self.trade_manager.trade(self.contract,
                                            quantity=target_quantity-self.current_position,
                                            order_type='MKT',
                                            urgency='Patient',
                                            orderRef= self.strategy_symbol,
                                            useRth=True)
        elif target_quantity < self.current_position:
            # Sell
            trade = self.trade_manager.trade(self.contract,
                                            quantity=target_quantity-self.current_position,
                                            order_type='MKT',
                                            urgency='Patient',
                                            orderRef= self.strategy_symbol,
                                            useRth=True)
        trade.fillEvent += self.on_fill
        trade.statusEvent += self.on_status_change
        return trade

    def disconnect(self):
        """Disconnect logic for the IB client"""
        disconnect_from_IB(ib=self.ib, symbol=self.strategy_symbol)
