from ib_async import *
import asyncio
from broker.trademanager import TradeManager
from broker import connect_to_IB, disconnect_from_IB
from data_and_research import get_strategy_allocation_bounds, get_strategy_symbol
from gui.log import add_log

from data_and_research import ac




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

        # Connect to Universe
        self.univ_library = ac.get_library('universe', create_if_missing=True)
        self.universe = self.univ_library.read('us_stocks').data
        
        # Position Management
        self.update_investment_status()
        self.target_weight, self.min_weight, self.max_weight = get_strategy_allocation_bounds(self.strategy_symbol)


    def run(self):
        add_log(f"{self.strategy_symbol} Thread Started")

        # Add Trading logic
        
        # 1) Access & filter trading universe 
        self.universe = self.filter_universe()
       
        
        # trade.fillEvent += self.on_fill

    def filter_universe(self):
        # consider only Stock with Price > 5 USD 
        self.universe = self.universe[self.universe['Close']>5]

        # trading volume > 25m USD
        self.universe = self.universe['Close']
       
    def update_investment_status(self):
        """ Update the investment status of the strategy """
        # TODO: Make use of the portfoliomanager
        positions_df = self.strategy_manager.portfolio_manager.match_ib_positions_with_arcticdb().copy()
        self.positions_df = positions_df[positions_df['strategy']==self.strategy_symbol]

        self.current_weight = self.positions_df['% of nav'].sum()
        
    
    def on_fill(self, trade, fill):
        # Handle fill event
        self.strategy_manager.message_queue.put({
            'type': 'fill',
            'strategy': self.strategy_symbol,
            'trade': trade,
            'fill': fill
        })

    def disconnect(self):
        # Disconnect logic for the IB client
        disconnect_from_IB(ib=self.ib,symbol=self.strategy_symbol)

