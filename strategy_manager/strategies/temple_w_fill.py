from ib_async import *
import asyncio, time, sys, traceback
from broker.trademanager import TradeManager
from broker import connect_to_IB, disconnect_from_IB
from data_and_research import get_strategy_allocation_bounds, get_strategy_symbol
from gui.log import add_log

PARAMS = {}
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
    strategy.disconnect()
    
class Strategy:
    def __init__(self, client_id, strategy_manager):
        self.client_id = client_id
        self.strategy_manager = strategy_manager
        self.filename = self.__class__.__module__ +".py"
        self.strategy_symbol = get_strategy_symbol(self.filename)
        
        # Get Data on Strategy Initialization
        self.ib = connect_to_IB(clientid=self.client_id, symbol=self.strategy_symbol)
        self.trade_manager = TradeManager(self.ib,self.strategy_manager)
        
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
    
    def on_status_change(self, trade):
        # Handle status change event
        self.strategy_manager.message_queue.put({
            'type': 'status_change',
            'strategy': self.strategy_symbol,
            'trade': trade,
            'status': trade.orderStatus.status,
            'info': f'Status Change message sent from {self.strategy_symbol}'
        })
    def start(self):
        self.run()
    
    def run(self):
        # Add Trading logic

        contract = Stock('AAPL', 'SMART', 'USD')
        #trade = self.trade_manager.trade(contract,1,order_type='LMT',limit=1,orderRef=self.strategy_symbol,urgency='Urgent',useRth=True)
        trade = self.trade_manager.trade(contract,-3,order_type='MKT',orderRef=self.strategy_symbol,urgency='Urgent',useRth=True)

        trade.fillEvent += self.on_fill
        trade.statusEvent += self.on_status_change
        # contract = Stock('CID','SMART','USD')
        # trade = self.trade_manager.trade(contract,-400,order_type='MKT',orderRef=self.strategy_symbol,urgency='Urgent',useRth=True)
        # self.ib.sleep(1)
        # Assign callbacks for order updates


        
        while True:
            self.ib.sleep(20)
        # while True:
        #     # This integrates the ib_insync event loop
        #     if trade.orderStatus.status == "Cancelled":
        #     #     print(trade)
        #         break
        #     # Additional strategy logic here
        #     self.ib.sleep(1)
        #     if trade.order and trade.orderStatus.status != "Cancelled":
        #         trade = self.ib.cancelOrder(trade.order)
                
                # print(trade.orderStatus.status)

            # if trade.isActive():
            #     print("is active")
            # if trade.isDone():
            #     print("done!")
            #     print(trade)
            
            #     self.ib.sleep(2)
            #     time.sleep(5)
            

                

    def disconnect(self):
        # Disconnect logic for the IB client
        disconnect_from_IB(ib=self.ib,symbol=self.strategy_symbol)

