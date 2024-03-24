from ib_insync import *
import asyncio
from broker.trademanager import TradeManager
from broker import connect_to_IB, disconnect_from_IB
from data_and_research import get_strategy_allocation_bounds, get_strategy_symbol
from gui.log import add_log

PARAMS = {}
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
        print(f"Error when instantiating: {e}")

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
        
        # Get Data on Strategy Initialization
        self.ib = connect_to_IB(clientid=self.client_id, symbol=self.strategy_symbol)
        self.trade_manager = TradeManager(self.ib)
        
        # Position Management
        self.update_investment_status()
        self.target_weight, self.min_weight, self.max_weight = get_strategy_allocation_bounds(self.strategy_symbol)
       
    def update_investment_status(self):
        """ Update the investment status of the strategy """
        # TODO: Make use of the portfoliomanager
        pass
    
    def on_fill(self, trade, fill):
        # Handle fill event
        self.strategy_manager.message_queue.put({
            'type': 'fill',
            'strategy': self.strategy_symbol,
            'trade': trade,
            'fill': fill
        })

    def run(self):
        add_log(f"{self.strategy_symbol} Thread Started")
        # Add Trading logic
        contract = Stock('AAPL', 'SMART', 'USD')
        trade = self.trade_manager.trade(contract,1,orderRef=self.strategy_symbol)

        # Assign callbacks for order updates
        trade.fillEvent += self.on_fill

    def disconnect(self):
        # Disconnect logic for the IB client
        disconnect_from_IB(ib=self.ib,symbol=self.strategy_symbol)

