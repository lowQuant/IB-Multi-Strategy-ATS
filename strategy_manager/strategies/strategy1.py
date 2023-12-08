# strategy_manager/strategies/strategy1.py

from gui.log import add_log, start_event
import time

class Strategy:
    def __init__(self, ib_client):
        self.ib = ib_client

    def run(self):
        add_log("Strategy1 Thread Started")
        start_event.wait()
        add_log("Executing Strategy 1")
        while start_event.is_set():
            time.sleep(1)
            add_log(f"S1: Buying 10 shares AAPL")

    def stop(self):
        # Hier Logik zum Stoppen der Strategie hinzufügen
        pass

def run(ib):
    strategy = Strategy(ib)
    strategy.run()