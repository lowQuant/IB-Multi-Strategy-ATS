import numpy as np
import pandas as pd
import datetime
from ib_async import *
from data_and_research import get_strategy_allocation_bounds, fetch_strategy_params
from broker.trademanager import TradeManager
from gui.log import add_log, start_event

# Global parameters that can be adjusted in the settings menu
PARAMS = {
    "Moving Average": 50,
    "ATR length": 20,
    "ATR Multiplier":3,
    "Position Sizing":-0.05,
    "Universe": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NFLX"]  # Replace with actual symbols of "Magnificent Seven"
}

class Strategy:
    def __init__(self, ib_client, strategy_manager, trade_manager):
        self.ib = ib_client
        self.strategy_manager = strategy_manager
        self.trade_manager = trade_manager
        self.strategy_symbol = "MAG7"

        # Initialize strategy state
        self.stock_data = {}
        self.current_positions = {}

    def run(self):
        # Main strategy execution loop
        while True:
            self.update_data()
            self.evaluate_positions()
            self.ib.sleep(1)  # Pause for a second before the next loop iteration

    def update_data(self):
        # Fetch and update price and indicator data for each stock
        universe = fetch_strategy_params(self.strategy_symbol)["Universe"]
        for symbol in universe: 
            print(f"Retrieving data for {symbol}")
            # self.stock_data[symbol] = self.fetch_stock_data(symbol)

    # def fetch_stock_data(self, symbol):
    #     # Fetch historical data and calculate indicators for a stock
    #     bars = self.ib.reqHistoricalData(
    #         contract=Stock(symbol, 'SMART', 'USD'),
    #         endDateTime='',
    #         durationStr='60 D',
    #         barSizeSetting='1 day',
    #         whatToShow='TRADES',
    #         useRTH=True,
    #         formatDate=1
    #     )
    #     df = pd.DataFrame(bars)
    #     df['MA50'] = calculate_moving_average(df['close'], PARAMS["Moving Average Window"])
    #     df['ATR20'] = calculate_atr(df, PARAMS["ATR Window"])
    #     return df

    # def evaluate_positions(self):
    #     # Evaluate and manage positions based on strategy logic
    #     for symbol, data in self.stock_data.items():
    #         current_price = data['close'].iloc[-1]
    #         ma50 = data['MA50'].iloc[-1]
    #         atr20 = data['ATR20'].iloc[-1]
    #         self.manage_position(symbol, current_price, ma50, atr20)

    # def manage_position(self, symbol, current_price, ma50, atr20):
    #     # Logic to manage individual positions
    #     if current_price < ma50:
    #         self.enter_short_position(symbol, current_price, atr20)

    # def enter_short_position(self, symbol, current_price, atr20):
    #     # Enter a short position with a trailing stop loss
    #     if symbol not in self.current_positions:
    #         # Calculate the number of shares to short based on account equity and max weight
    #         account_equity = self.get_account_equity()
    #         max_shares =