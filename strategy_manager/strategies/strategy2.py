# strategy_manager/strategies/strategy1.py

from gui.log import add_log, start_event
import time

class Strategy:
    def __init__(self, ib_client):
        self.ib = ib_client

    def run(self):
        add_log("Strategy2 Thread Started")
        start_event.wait()
        
        while start_event.is_set():
            add_log("Executing Strategy 2")
            time.sleep(4)
            add_log("S2: Listening to market data")

    def stop(self):
        # Hier Logik zum Stoppen der Strategie hinzufügen
        pass

def run(ib):
    strategy = Strategy(ib)
    strategy.run()