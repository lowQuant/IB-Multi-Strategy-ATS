# strategy_manager/strategy_manager.py

import importlib.util
import os, queue, datetime
import threading, asyncio
import pandas as pd

from gui.log import add_log
from broker import connect_to_IB,disconnect_from_IB
from broker.trademanager import TradeManager
from broker.portfoliomanager import PortfolioManager

from data_and_research.utils import fetch_strategies
from data_and_research.data_manager import DataManager

class StrategyManager:
    def __init__(self):
        self.clientId = 0
        print("instantiated StrategyManager")
        self.ib_client = connect_to_IB(clientid=self.clientId)
        self.strategy_threads = []
        self.strategies = []
        self.trade_manager = TradeManager(ib_client=self.ib_client,strategy_manager=self)
        self.portfolio_manager = PortfolioManager(ib_client=self.ib_client)
        self.data_manager = DataManager(ib_client= self.ib_client)
        
        self.message_queue = queue.Queue()

        # Start the message processing thread with a flag indicating loop creation
        self.create_loop_in_thread = True
        self.message_processor_thread = threading.Thread(target=self.process_messages)
        self.message_processor_thread.daemon = True
        self.message_processor_thread.start()

    def process_messages(self):
        if self.create_loop_in_thread:
            # Create the event loop within the thread
            self.loop = asyncio.new_event_loop()  # Create a new event loop
            asyncio.set_event_loop(self.loop)  # Set the loop for the current thread
            self.create_loop_in_thread = False  # Only create the loop once
        try:
            while True:
                message = self.message_queue.get(block=True)  # Wait for a message
                self.handle_message(message)  # Process the received message
        except Exception as e:
            print(f"Error processing message: {e}")
        finally:
            # Close the event loop when exiting the thread
            if hasattr(self, 'loop'):  # Check if loop exists before closing
                self.loop.close()

    def handle_message(self, message):
        # Implement your logic to handle different message types
        try:
            print(f"Received message: Type: {message['type'].upper()} [{message['strategy']}]") #[{message}]")  # Example message handling
        except Exception as e:
            print(f"Exception occured in handling message from queue: {e}")
        if message['type'] == 'order':
            self.notify_order_placement(message['strategy'], message['trade'])
        elif message['type'] == 'fill':
            self.handle_fill_event(message['strategy'],message['trade'],message['fill'])
        elif message['type'] == 'status_change':
            self.handle_status_change(message['strategy'], message['trade'], message['status'])
        self.message_queue.task_done()

    def notify_order_placement(self, strategy, trade):
        symbol = trade.contract.symbol if hasattr(trade.contract, 'symbol') else "N/A"
        order_type = trade.order.orderType
        action = trade.order.action
        quantity = trade.order.totalQuantity

        if trade.isDone():
            add_log(f"{trade.fills[0].execution.side} {trade.orderStatus.filled} {trade.contract.symbol}@{trade.orderStatus.avgFillPrice} [{trade.order.orderRef}]")
            self.portfolio_manager.process_new_trade(strategy, trade)
        else:
            add_log(f"{order_type} Order placed: {action} {quantity} {symbol} [{strategy}]")
            
    def handle_fill_event(self, strategy_symbol, trade, fill):
        print("from handle_fill_event:")
        print(trade)
        add_log(f"{trade.fills[0].execution.side} {trade.orderStatus.filled} {trade.contract.symbol}@{trade.orderStatus.avgFillPrice} [{strategy_symbol}]")
        
        # # Save and mark trade in the global portfolio
        self.portfolio_manager.process_new_trade(strategy_symbol, trade)
        # current_portfolio_df = self.portfolio_manager.match_ib_positions_with_arcticdb()

    def handle_status_change(self, strategy_symbol, trade, status):
        if "Pending" not in status:
            add_log(f"{status}: {trade.order.action} {trade.order.totalQuantity} {trade.contract.symbol} [{strategy_symbol}]")

    def disconnect(self):
        self.stop_all()

    def stop_all(self):
        """ Stop all running strategies and threads. """
        for thread in self.strategy_threads:
            thread.join(timeout=5)
        # Wait for the message processing thread to finish
        self.message_processor_thread.join(timeout=5)

        self.strategy_threads = []
        self.strategies = []

    def load_strategies(self):
        '''loads all active strategies that the user added via the Settings/Strategies Menu
            & stores them in self.strategies'''
        self.strategies.clear()
        strategy_dir = "strategy_manager/strategies"
        strategy_names, self.strategy_df = fetch_strategies()
        active_filenames = set(self.strategy_df[self.strategy_df["active"] == "True"]['filename'])
        
        if strategy_names:
            strategy_files = [f for f in self.strategy_df['filename'] if f in os.listdir(strategy_dir) and f in active_filenames]
            for file in strategy_files:
                strategy_path = os.path.join(strategy_dir, file)
                module_name = file[:-3]
                print("Loading strategy:", module_name)

                try:
                    spec = importlib.util.spec_from_file_location(module_name, strategy_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    if hasattr(module, 'Strategy'):
                        print(f"Instantiating strategy: {module_name}")
                        self.strategies.append(module)
                    else:
                        print(f"No 'Strategy' class found in {module_name}")
                except Exception as e:
                    print(f"Error loading strategy {module_name}: {e}")

            print("Loaded strategies:", [module_name])
        
    def start_all(self):
        self.load_strategies()

        # Update the Portfolio before going live with the strategies
        self.portfolio_manager.match_ib_positions_with_arcticdb()
        
        for strategy_module in self.strategies:
            if hasattr(strategy_module, 'manage_strategy'):
                self.clientId += 1
                thread = threading.Thread(target=strategy_module.manage_strategy, args=(self.clientId,self))
                thread.daemon = True
                thread.start()
                self.strategy_threads.append(thread)
            else:
                print(f"Strategy {type(strategy_module).__name__} does not have a manage_strategy function.")
    
    def disconnect(self):
        self.stop_all()

    def stop_message_queue(self):
        """Stop the message processing loop and close the event loop."""
        self.running = False
        self.loop.call_soon_threadsafe(self.loop.stop)

    def stop_all(self):
        """ Stop all running strategies and threads. """
        for thread in self.strategy_threads:
            thread.join(timeout=5)
        self.stop_message_queue()
        self.strategy_threads = []
        self.strategies = []
