# strategy_manager/strategy_manager.py

import importlib.util
import os, queue, datetime
import threading, asyncio
import pandas as pd
from data_and_research.utils import fetch_strategies
from gui.log import add_log
from broker import connect_to_IB,disconnect_from_IB
from broker.trademanager import TradeManager
from broker.portfolio import PortfolioManager

class StrategyManager:
    def __init__(self):
        self.clientId = 0
        print("instantiated StrategyManager")
        self.ib_client = connect_to_IB(clientid=self.clientId)
        self.strategy_threads = []
        self.strategies = []
        self.trade_manager = TradeManager(ib_client=self.ib_client,strategy_manager=self)
        self.portfolio_manager = PortfolioManager(ib_client=self.ib_client)
        
        self.message_queue = queue.Queue()

        # Start the message processing thread
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
            if hasattr(self, 'loop'):
                self.loop.close()
    
    def handle_message(self, message):
        # Implement your logic to handle different message types
        print(f"Received message: {message['info']}")  # Example message handling
        if message['type'] == 'order':
            self.notify_order_placement(message['strategy'], message['trade'])
        elif message['type'] == 'fill':
            self.handle_fill_event(message['strategy'], message['trade'], message['fill'])
        elif message['type'] == 'status_change':
            # Synchronous handling can remain as is
            self.handle_status_change(message['strategy'], message['trade'], message['status'])
        self.message_queue.task_done()

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

    def stop_all(self):
        """ Stop all running strategies and threads. """
        for thread in self.strategy_threads:
            thread.join(timeout=5)
        self.message_processor_thread.join(timeout=5)
        self.strategy_threads = []
        self.strategies = []

    def notify_order_placement(self, strategy, trade):
        symbol = trade.contract.symbol if hasattr(trade.contract, 'symbol') else "N/A"
        order_type = trade.order.orderType
        action = trade.order.action
        quantity = trade.order.totalQuantity

        add_log(f"{order_type} Order placed: {action} {quantity} {symbol} [{strategy}]")

    def handle_status_change(self, strategy_symbol, trade, status):
        # Implement status change handling logic        
        if "Pending" not in status: # not interested in pending order actions
            add_log(f"{status}: {trade.order.action} {trade.order.totalQuantity} {trade.contract.symbol} [{strategy_symbol}]")

    def handle_fill_event(self):
        pass
    
    # def notify_order_placement(self, strategy, trade):
    #     # Extracting order details for logging
    #     symbol = trade.contract.symbol if hasattr(trade.contract, 'symbol') else "N/A"
    #     order_type = trade.order.orderType
    #     action = trade.order.action
    #     quantity = trade.order.totalQuantity

    #     add_log(f"{order_type} Order placed: {action} {quantity} {symbol} [{strategy}]")

    #     # if trade.filled():
    #     #     print("Fill received immediately")
    #     #     self.message_queue.put({'type': 'fill','strategy': strategy,
    #     #                             'trade': trade,'fill': trade.fills})



    # async def handle_fill_event(self, strategy_symbol, trade, fill):
    #     # Asynchronous version of the function
    #     add_log(f"Fill received: {fill} [{strategy_symbol}]")
    #     print(fill)
    #     # Example async call within the handler, assume save_new_trade_in_global_portfolio_ac is async
    #     current_portfolio_df = await self.portfolio_manager.match_ib_positions_with_arcticdb()
    #     print("current portfolio")
    #     print(current_portfolio_df)
    #     if trade.isDone():
    #         add_log(f"Order filled for {strategy_symbol}: {fill}")

    # def handle_fill_event(self, strategy_symbol, trade, fill):
    #     '''Function that implements fill event handling logic'''
    #     add_log(f"Fill received: {fill} [{strategy_symbol}]")
    #     # Save and mark trade in the global portfolio
    #     self.portfolio_manager.save_new_trade_in_global_portfolio_ac(strategy_symbol,trade)
    #     current_portfolio_df = self.portfolio_manager.match_ib_positions_with_arcticdb()
        
    #     # Logging in the GUI
    #     if trade.isDone():
    #         add_log(f"Order filled for {strategy_symbol}: {fill}")


    # def handle_status_change(self, strategy_symbol, trade, status):
    #     # Implement status change handling logic        
    #     if "Pending" not in status: # not interested in pending order actions
    #         add_log(f"{status}: {trade.order.action} {trade.order.totalQuantity} {trade.contract.symbol} [{strategy_symbol}]")

    #     total_equity = sum(float(entry.value) for entry in self.ib_client.accountSummary() if entry.tag == "EquityWithLoanValue")
    #     print(total_equity)
    #     #!TODO: if "Cancel" in status: make sure order is marked as cancelled in ArcticDB
    #     # DO WE NEED ORDER TRACKING IN ARCTICDB? We are using orderref anyways??!
            

    def update_on_trade(self, strategy, trade_details):
        strategy_name = type(strategy).__name__
        # Calculate new cash position
        new_cash_position = self.calculate_cash_position(strategy_name, trade_details)
        
        # Update database
        self.update_database(strategy_name, trade_details, new_cash_position)

    def calculate_cash_position(self, strategy_name, trade_details):
        # Implement cash position calculation logic
        new_cash_position = 0
        return new_cash_position

    def update_database(self, strategy_name, trade_details, new_cash_position):
        # Implement database update logic
        # Use ArcticDB to update the "portfolio" library with the new trade and cash position
        pass