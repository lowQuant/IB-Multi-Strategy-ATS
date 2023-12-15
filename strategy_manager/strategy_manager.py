# strategy_manager/strategy_manager.py

import importlib.util
import os
import threading
from data_and_research.utils import fetch_strategies


class StrategyManager:
    def __init__(self, ib_client):
        self.ib_client = ib_client
        self.strategy_threads = []
        self.strategies = []
        self.load_strategies()

    def load_strategies(self):
        strategy_dir = "strategy_manager/strategies"
        strategy_names, self.strategy_df = fetch_strategies()
        # strategy_files = [f"{strategy}.py" for strategy in strategy_names if f"{strategy}.py" in os.listdir(strategy_dir)]
        strategy_files = [f for f in self.strategy_df['filename'] if f in os.listdir(strategy_dir)]
        print([f for f in self.strategy_df['filename']])
        print("Found strategy files:", strategy_files)

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
                    strategy_instance = module.Strategy(self.ib_client)
                    self.strategies.append(strategy_instance)
                else:
                    print(f"No 'Strategy' class found in {module_name}")
            except Exception as e:
                print(f"Error loading strategy {module_name}: {e}")

        print("Loaded strategies:", [type(s).__name__ for s in self.strategies])

    def start_all(self):
        for strategy in self.strategies:
            if hasattr(strategy, 'run'):
                thread = threading.Thread(target=strategy.run)
                thread.daemon = True
                thread.start()
                self.strategy_threads.append(thread)
            else:
                print(f"Strategy {type(strategy).__name__} does not have a run method.")


    def stop_all(self):
        # Implement logic to gracefully stop all strategies
        for strategy in self.strategies:
            strategy.stop()  # Assuming each strategy has a stop method
        for thread in self.strategy_threads:
            thread.join(timeout=5)
