# strategy_manager/strategies/strategy_template.py

import asyncio
import sys
import traceback
from ib_async import *
from broker import connect_to_IB, disconnect_from_IB
from broker.trademanager import TradeManager
from data_and_research import get_strategy_allocation_bounds, get_strategy_symbol, fetch_strategy_params
from gui.log import add_log

# Define default parameters; users can add more as needed. 
# The PARAMS will saved to ArcticDB when creating the strategy in the GUI.
# Users can edit the PARAMS in the GUI Settings/Strategies/Strategy Details
PARAMS = {
    # 'param1': 'value1',
    # 'param2': 'value2'
}

strategy = None

def manage_strategy(client_id, strategy_manager, strategy_loops):
    """
    Initialize and run the strategy within its own asyncio event loop.

    Args:
        client_id (int): Unique identifier for the strategy instance.
        strategy_manager (StrategyManager): The managing StrategyManager instance.
        strategy_loops (dict): Dictionary to store the event loop references.
    """
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

        # Run the event loop indefinitely
        loop.run_forever()

    except Exception as e:
        # Get the current exception information
        _, _, exc_traceback = sys.exc_info()
        
        # Extract the last frame (most recent call) from the traceback
        tb_frame = traceback.extract_tb(exc_traceback)[-1]
        filename = tb_frame.filename
        line_number = tb_frame.lineno
        
        # Print detailed error information
        print(f"Error in {filename}, line {line_number}: {str(e)}")
        print("Full traceback:")
        traceback.print_exc()

    finally: 
        # Clean up and disconnect
        disconnect_from_IB(strategy.ib, strategy.strategy_symbol)
        loop.close()
        # Remove the loop reference from the shared dictionary
        del strategy_loops[client_id]

class Strategy:
    """
    Base Strategy class. Users should inherit from this class and override necessary methods.
    """
    def __init__(self, client_id, strategy_manager):
        """
        Initialize the Strategy instance.

        Args:
            client_id (int): Unique identifier for the strategy instance.
            strategy_manager (StrategyManager): The managing StrategyManager instance.
        """
        global PARAMS
        self.client_id = client_id
        self.strategy_manager = strategy_manager
        self.filename = self.__class__.__module__ +".py"
        self.strategy_symbol = get_strategy_symbol(self.filename)

        # Connect to Interactive Brokers
        self.ib = connect_to_IB(clientid=self.client_id, symbol=self.strategy_symbol)
        self.trade_manager = TradeManager(self.ib, self.strategy_manager)

        # Initialize any additional strategy parameters here
        self.initialize_strategy()

    def initialize_strategy(self):
        """
        Initialize strategy-specific parameters and data.
        """
        self.target_weight, self.min_weight, self.max_weight = get_strategy_allocation_bounds(self.strategy_symbol)
        # Example: Initialize data structures or load configuration
        pass

    async def run(self):
        """
        Main asynchronous loop to execute trading strategy logic.
        Users should implement their strategy's main logic here.
        """
        contract = Stock('AAPL', 'SMART', 'USD')
        #trade = self.trade_manager.trade(contract,1,order_type='LMT',limit=1,orderRef=self.strategy_symbol,urgency='Urgent',useRth=True)
        trade = self.trade_manager.trade(contract,1,order_type='MKT',orderRef=self.strategy_symbol,urgency='Urgent',useRth=True)

        trade.fillEvent += self.on_fill
        trade.statusEvent += self.on_status_change

        # contract = Stock('CID','SMART','USD')
        while True:
            # Example placeholder for strategy logic
            await asyncio.sleep(1)  # Replace with actual strategy execution steps


    def start(self):
        """
        Schedule the asynchronous run method in the event loop.
        """
        asyncio.ensure_future(self.run())
        # For Python 3.7+, you can also use:
        # asyncio.create_task(self.run())


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
    
    def update_investment_status(self):
        """Update the investment status of the strategy"""
        self.positions_df = self.strategy_manager.portfolio_manager.match_ib_positions_with_arcticdb()
        self.positions_df = self.positions_df[self.positions_df['symbol'] == self.strategy_symbol]

        self.current_position = int(self.positions_df['position'].iloc[-1]) if not self.positions_df.empty else 0
    
    def place_order(self, con, qty, ordertype, algo = True, urgency='Patient', orderRef = "", limit = None, useRth=True):
        """
        A wrapper for the trade_manager.trade method. That was created to assign callbacks to the trade object.

        Args:
            con (Contract): The contract to trade.
            qty (int): The quantity to trade.
            ordertype (str): The type of order (e.g., 'MKT', 'LMT').
            algo (bool, optional): Whether to use an algorithm for the order. Defaults to True.
            urgency (str, optional): The urgency of the order. Defaults to 'Patient'.
            orderRef (str, optional): A reference for the order. Defaults to "".
            limit (float, optional): The limit price for limit orders. Defaults to None.
            useRth (bool, optional): Whether to use regular trading hours. Defaults to True.

        Returns:
            Trade: The trade object representing the placed order.
        """
        trade = self.trade_manager.trade(con,quantity=qty,order_type=ordertype,urgency=urgency,orderRef=orderRef,useRth=useRth)
        
        # Assign callbacks for order updates
        trade.fillEvent += self.on_fill
        trade.statusEvent += self.on_status_change
        
        return trade