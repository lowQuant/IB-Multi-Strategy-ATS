# ac/utils.py
import numpy as np
import pandas as pd
from datetime import datetime
from arcticdb import Arctic, QueryBuilder

def initialize_db(db_path):
    global ac
    ac_local = Arctic(f'lmdb://{db_path}?map_size=200MB')
    
    if not "settings" in ac_local.list_libraries():
        print("Creating settings a new settings table")
        library = ac_local.get_library('settings', create_if_missing=True)
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
        return ac
    
    else: # read local settings if settings table exists
        library = ac_local.get_library('settings', create_if_missing=True)
        settings_df = library.read("settings").data
        
        # if S3 is set, change ac from local to s3
        if settings_df.loc["s3_db_management","Value"] == str(True):
            region = settings_df.loc["region","Value"]
            bucket_name = settings_df.loc["bucket_name","Value"]
            id = settings_df.loc["aws_access_id","Value"]
            key = settings_df.loc["aws_access_key","Value"]
        
            ac =Arctic(f's3://s3.{region}.amazonaws.com:{bucket_name}?region={region}&access={id}&secret={key}')

            # check if "settings" exists in s3 ac
            if not "settings" in ac.list_libraries():
                lib = ac.get_library('settings', create_if_missing=True)
                # copy settings from local ac
                lib.write("settings", settings_df)
        else:
            ac = ac_local
        return ac

ac = initialize_db("data_and_research/db")
