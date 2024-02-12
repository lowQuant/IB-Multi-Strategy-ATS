# ac/utils.py
import numpy as np
import pandas as pd
from datetime import datetime
import importlib.util
from pathlib import Path
from arcticdb import Arctic, QueryBuilder, LibraryOptions

# Create LibraryOptions with dynamic_schema enabled
LIBRARY_OPTIONS = LibraryOptions(dynamic_schema=True)

def initialize_db(db_path):
    global ac
    ac_local = Arctic(f'lmdb://{db_path}?map_size=5MB')
    
    if not "general" in ac_local.list_libraries():
        print("Creating library 'general' where *settings and *strategies will be stored")
        library = ac_local.get_library('general', create_if_missing=True)
        index_values = ['port', 
                        's3_db_management', # False for local
                        'aws_access_id', 'aws_access_key',
                        'bucket_name','region',
                        'start_tws','username','password']
        
        data = {'Value': ["7497", # default port
                        "False", # defaul local
                        "", "", # aws_access_id, key
                        "", "", # bucket_name, region
                        "False","","" # Start TWS Automatically default False
                        ]}
        df = pd.DataFrame(data, index=index_values)
        library.write(symbol="settings",data=df)
        ac = ac_local
        
    else: # read local settings if settings table exists
        library = ac_local.get_library('general', create_if_missing=True)
        settings_df = library.read("settings").data
        
        # if S3 is set, change ac from local to s3
        if settings_df.loc["s3_db_management","Value"] == str(True):
            region = settings_df.loc["region","Value"]
            bucket_name = settings_df.loc["bucket_name","Value"]
            id = settings_df.loc["aws_access_id","Value"]
            key = settings_df.loc["aws_access_key","Value"]
        
            ac =Arctic(f's3://s3.{region}.amazonaws.com:{bucket_name}?region={region}&access={id}&secret={key}')

            # check if "settings" exists in s3 ac
            if not "general" in ac.list_libraries():
                lib = ac.get_library('general', create_if_missing=True)
                # copy settings from local ac
                lib.write("settings", settings_df)
        else:
            ac = ac_local

    # Create library portfolio
    if not "portfolio" in ac.list_libraries():
        print("Creating library 'portfolio' that will keep track of our strategies' positions")
        library = ac.get_library('portfolio', create_if_missing=True, library_options=LIBRARY_OPTIONS)
    
    # Create other libraries here later (e.g. universe, stocks, futures etc.) 
    return ac

ac = initialize_db("data_and_research/db")

def fetch_strategies():
    lib = ac.get_library('general', create_if_missing=True)
    if lib.has_symbol("strategies"):
        strat_df = lib.read("strategies").data
        # print("library 'strategies' cols: ",strat_df.columns)
        strategies = strat_df.index.to_list()
        # print("strategies:" , strategies)
    else:
        strategies = []
        strat_df = pd.DataFrame()
    return strategies, strat_df

def fetch_strategy_params(strategy_symbol):
    lib = ac.get_library('general', create_if_missing=True)
    if lib.has_symbol("strategies"):
        strat_df = lib.read("strategies").data
        params = strat_df.loc[strategy_symbol,"params"]
        if params:
            try:
                params_dict = eval(params)  # Converts string to dictionary
                print("loaded params from our db")
                return params_dict
            except:
                return params # returns params on error as params is probably a string (Error Code)
        else:
            strategy_file = strat_df.loc[strategy_symbol,"filename"]
            print(f"Fetching PARAMS from {strategy_file}")
            params = load_params_from_module(strategy_file)

            if params:
                print("Updating the database")
                update_params_in_db(strategy_symbol, params)  # Update the database
                return params
    
def load_params_from_module(strategy_file):
    """
    Dynamically load a strategy module given the strategy file name and extract its params.
    """
    # Get the absolute path of the current file (settings_window.py)
    current_file_path = Path(__file__).resolve()

    # Get the root directory of the project (IB-Multi-Strategy-ATS)
    project_root = current_file_path.parent.parent

    # Construct the full path to the strategy file
    strategy_module_path = project_root / "strategy_manager" / "strategies" / strategy_file

    module_name = strategy_file.split(".")[0]
    try:
        spec = importlib.util.spec_from_file_location(module_name, str(strategy_module_path))
        if spec and spec.loader:
            strategy_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(strategy_module)
            if hasattr(strategy_module, 'PARAMS'):
                return strategy_module.PARAMS
            else:
                print(f"No 'params' found in {module_name}")
        else:
            print(f"Module spec not found for {module_name}")
    except Exception as e:
        return e
    
def update_params_in_db(strategy_symbol, params):
    lib = ac.get_library('general')
    strat_df = lib.read("strategies").data
    print(strat_df)
    # Update only the 'params' column for the specific strategy
    if strategy_symbol in strat_df.index:
        strat_df.at[strategy_symbol, "params"] = str(params)  # Update the params
        lib.write("strategies", strat_df, metadata={'source': 'manual update'})
        #lib.update("strategies", strat_df.loc[[strategy_symbol]], metadata={'source': 'manual update'})
        print(f"Updated params for {strategy_symbol} in the database.")
    else:
        print(f"Strategy {strategy_symbol} not found in the database.")

def get_strategy_symbol(filename):
    try:
        lib = ac.get_library('general')
        df = lib.read("strategies").data
        symbol = df[df.filename == filename].index.item()  # Using .item() to get the actual symbol
        return symbol
    except Exception as e:
        print(f"Error retrieving strategy symbol: {e}")
        return None

def get_strategy_allocation_bounds(strategy_symbol):
    lib = ac.get_library('general')
    strat_df = lib.read("strategies").data
    if strategy_symbol in strat_df.index:
        try:
            target_weight = strat_df.loc[strategy_symbol, "target_weight"] or 0
            min_weight = strat_df.loc[strategy_symbol, "min_weight"] or 0
            max_weight = strat_df.loc[strategy_symbol, "max_weight"] or 0
        except ValueError:
            print(f"Invalid weight values for strategy {strategy_symbol}")
            return 0.0, 0.0, 0.0  # Default values

        print(f"The Allocation bounds are target:{target_weight}, min:{min_weight}, max:{max_weight}")
        return float(target_weight), float(min_weight), float(max_weight)
    else:
        print(f"Strategy {strategy_symbol} not found in the database.")
        return 0.0, 0.0, 0.0  # Default values

def update_weights(strategy_symbol,target_weight,min_weight,max_weight):
    lib = ac.get_library('general')
    strat_df = lib.read("strategies").data
    if strategy_symbol in strat_df.index:
        strat_df.at[strategy_symbol, "target_weight"] = str(target_weight) 
        strat_df.at[strategy_symbol, "min_weight"] = str(min_weight)
        strat_df.at[strategy_symbol, "max_weight"] = str(max_weight)
        lib.write("strategies", strat_df, metadata={'source': 'manual update'})
        print(f"Updated weights for {strategy_symbol} in the database.")
    else:
        print(f"Strategy {strategy_symbol} not found in the database.")