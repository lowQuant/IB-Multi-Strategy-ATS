import pandas as pd
import time, os, threading, subprocess, schedule, socket
from ib_async import *
from gui.log import add_log
import datetime
import yfinance as yf
from data_and_research import ac, initialize_db

class DataManager:
    def __init__(self, ib_client: IB,arctic = None):
        self.ib = ib_client
        self.arctic = arctic if arctic else ac
        self.account_id = self.ib.managedAccounts()[0]
        
    def save_new_job(self, filename, cron_notation, operating_system):
        '''Function to save a scheduled task/job to ArcticDB'''
        jobs_df = pd.DataFrame([{"filename": filename,"cron_notation": cron_notation,
              "operating_system": operating_system, "hostname": socket.gethostname()}])
        
        self.jobs_lib = self.arctic.get_library('jobs', create_if_missing=True)

        if 'jobs' in self.jobs_lib.list_symbols():
            self.jobs_lib.append('jobs',jobs_df)
        else:
            self.jobs_lib.write('jobs',jobs_df)
        
    def get_saved_jobs(self):
        # Retrieve saved jobs for the account_id
        try:
            self.jobs_lib = self.arctic.get_library('jobs', create_if_missing=True)
            jobs_df = self.jobs_lib.read("jobs").data
            return jobs_df
        except Exception:  # Handle case where there are no saved jobs
            return pd.DataFrame(columns=["filename", "cron_notation", "operating_system","hostname"])
        
    def get_data_from_arctic(self, library_name, symbol):
        """
        Retrieve data for a given symbol from the specified Arctic library.
        """
        try:
            lib = self.arctic.get_library(library_name)
            data = lib.read(symbol).data
            return data.sort_index(ascending=False)
        except Exception as e:
            print(f"Error retrieving data from Arctic: {e}")
            return None
    
    def run_python_script(self, script_path):
        """
        Execute an external Python script located at script_path.
        """
        if os.path.exists(script_path) and script_path.endswith('.py'):
            try:
                result = subprocess.run(['python', script_path], capture_output=True, text=True)
                print("Script output:", result.stdout)
                print("Script errors:", result.stderr)
                return result
            except subprocess.CalledProcessError as e:
                print(f"An error occurred while running the script: {e}")
        else:
            print("Invalid script path or file is not a Python script.")

    def schedule_python_script(self, script_path, schedule_time):
        """
        Schedule a Python script to run at a specific time.
        """
        schedule.every().day.at(schedule_time).do(self.run_python_script, script_path)
        print(f"Scheduled {script_path} to run daily at {schedule_time}")
        
        # Start a thread to run the scheduler
        threading.Thread(target=self.run_scheduler, daemon=True).start()

    def run_scheduler(self):
        """
        Continuously run the scheduled jobs.
        """
        while True:
            schedule.run_pending()
            time.sleep(1)