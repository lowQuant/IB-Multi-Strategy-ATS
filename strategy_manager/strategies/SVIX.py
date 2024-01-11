# strategy_manager/strategies/SVIX.py

from gui.log import add_log, start_event
from ib_insync import *
import time, asyncio

PARAMS = {}

class Strategy:
    def __init__(self, ib_client,strategy_manager,trade_manager):
        self.ib = ib_client
        self.strategy_symbol = "SVIX"
        self.strategy_manager = strategy_manager
        self.trade_manager = trade_manager

    def run(self):
        # Uncomment below if async functions are called
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            add_log("Strategy SVIX Thread Started")
            contract = Stock('AAPL', 'SMART', 'USD')
            order = MarketOrder('BUY', 10)
            order.orderRef = self.strategy_symbol
            add_log(f"{order}")
            trade = self.ib.placeOrder(contract, order)

            # Assign callbacks for order updates
            trade.fillEvent += self.on_fill
            trade.statusEvent += self.on_status_change

            while start_event.is_set():
                add_log("in the while loop")
                # This integrates the ib_insync event loop
                # Additional strategy logic here
                self.ib.sleep(1)
                if trade.order:
                    self.ib.cancelOrder(trade.order)
                
        except Exception as e:
            add_log(f"Error in SVIX run method: {e}")
        finally:
            loop.close()
        
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
            'status': trade.orderStatus.status
        })

    def stop(self):
        # Hier Logik zum Stoppen der Strategie hinzufügen
        pass
    
        # self.strategy_manager.message_queue.put({
        #     'type': 'order',
        #     'strategy': 'ExampleStrategy',
        #     'trade': trade
        # })
        #trade.newOrderEvent += self.on_updates

    

        # add_log("Strategy SVIX Thread Started")
        # start_event.wait()
        
        # while start_event.is_set():
        #     add_log("Executing Strategy SVXY")
        #     time.sleep(1)
        #     add_log(f"S1: Buying 10 shares AAPL")
        #     time.sleep(3)

 

# def run(ib):
#     strategy = Strategy(ib)
#     strategy.run()
    


    # def on_updates(self, trade: Trade, update: str):
    #     if trade.orderStatus.status == 'Filled':
    #         # Handle filled order
    #         trade_details = await self.get_trade_details(trade)
    #         self.strategy_manager.notify_trade_update(self.strategy_symbol, trade_details)

    #     elif trade.orderStatus.status in ['Submitted', 'PreSubmitted']:
    #         # Handle order submission
    #         self.strategy_manager.notify_order_placement(self.strategy_symbol, trade)
    #         add_log(f"{trade}")