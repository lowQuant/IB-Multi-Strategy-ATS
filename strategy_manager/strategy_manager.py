# strategy_manager/strategy_manager.py

import importlib.util
import os
import threading


class StrategyManager:
    def __init__(self, ib_client):
        self.ib_client = ib_client
        self.strategy_threads = []
        self.strategies = []
        self.load_strategies()

    def load_strategies(self):
        strategy_dir = "strategy_manager/strategies"
        strategy_files = [f for f in os.listdir(strategy_dir) if f.endswith('.py') and not f.startswith('__')]
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

        print("Loaded strategies:", self.strategies)

        # strategies = [f[:-3] for f in os.listdir("strategy_manager/strategies") if f.endswith('.py') and 'strategy' in f]
        # for strategy_name in strategies:
        #     strategy_module = load_strategy(strategy_name)
        #     if strategy_module and hasattr(strategy_module, 'run'):
        #         t = threading.Thread(target=strategy_module.run) #,args=(ib_client, start_event,))
        #         t.daemon = True
        #         t.start()
        #         strategy_threads.append(t)

    def start_all(self):
        for strategy in self.strategies:
            thread = threading.Thread(target=strategy.run)
            thread.daemon = True
            thread.start()
            self.strategy_threads.append(thread)

    def stop_all(self):
        # Implement logic to gracefully stop all strategies
        for strategy in self.strategies:
            strategy.stop()  # Assuming each strategy has a stop method
        for thread in self.strategy_threads:
            thread.join(timeout=5)
