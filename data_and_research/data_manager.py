import pandas as pd
import time, os, threading, subprocess, schedule, socket
from ib_async import *
import datetime
import importlib.util, argparse
import yfinance as yf
try:
    from data_and_research import ac, initialize_db
except:
    from utils import ac, initialize_db

class DataManager:
    def __init__(self, ib_client: IB,arctic = None):
        self.arctic = arctic if arctic else ac
        if ib_client:
            self.ib = ib_client
            self.account_id = self.ib.managedAccounts()[0]

    def store_data_from_external_scripts(self, script_name, library, symbol, append=False):
        """
        Load and execute the function from the script, retrieve the DataFrame,
        and store it in ArcticDB.
        
        Parameters:
        - script_name: The file path of the script.
        - library: The ArcticDB library where the data will be stored.
        - symbol: The symbol under which the data will be stored.
        """
        # Dynamically load and execute the script
        spec = importlib.util.spec_from_file_location("module.name", script_name)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Assume the script has a main function that returns a DataFrame
        df = module.main()  # Adjust based on your script's logic

        # Store the DataFrame in ArcticDB
        lib = self.arctic.get_library(library,create_if_missing=True)

        if symbol in lib.list_symbols():
            if append:
                lib.append(symbol,df)
            else:
                lib.write(symbol,df)
        else:
            lib.write(symbol,df)

        print(f"Data from {script_name} stored successfully in {library}/{symbol}.")
        
    def save_new_job(self, filename, cron_notation, cron_command, operating_system, execution_method,lib="",symbol="",saving_method="Replace"):
        '''Function to save a scheduled task/job to ArcticDB'''
        if execution_method == 'Centralized':
            job_data = {"filename": filename,"cron_notation": cron_notation,
                "operating_system": operating_system, "hostname": socket.gethostname(),
                "execution_method": execution_method, "arctic_path":f"{lib}/{symbol}",
                "replace": str(True) if saving_method == 'Replace' else str(False)}
            if operating_system == 'macOS':
                job_data["cron_command"] = cron_command
        else:
            job_data = {"filename": filename,"cron_notation": cron_notation,
                "operating_system": operating_system, "hostname": socket.gethostname(),
                "execution_method": execution_method, "arctic_path":"","replace": ""}
            
            if operating_system == 'macOS':
                job_data["cron_command"] = cron_command

        jobs_df = pd.DataFrame([job_data])
        self.jobs_lib = self.arctic.get_library('jobs', create_if_missing=True)

        if 'jobs' in self.jobs_lib.list_symbols():
            if not self.jobs_lib.read('jobs').data.empty:
                self.jobs_lib.append('jobs',jobs_df)
            else:
                self.jobs_lib.write('jobs',jobs_df)
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


def main():
    parser = argparse.ArgumentParser(description="Manage data jobs with DataManager.")
    
    # Add arguments for various tasks
    parser.add_argument('--store-data', action='store_true', help="Store data from an external script.")
    parser.add_argument('--script', help="Path to the external script.")
    parser.add_argument('--library', help="ArcticDB library to store the data.")
    parser.add_argument('--symbol', help="Symbol under which the data will be stored.")
    
    parser.add_argument('--run-script', action='store_true', help="Run an external Python script.")
    parser.add_argument('--script-path', help="Path to the Python script to run.")
    
    parser.add_argument('--schedule-script', action='store_true', help="Schedule a Python script.")
    parser.add_argument('--schedule-time', help="Time to run the scheduled script (e.g., 14:30).")
    
    args = parser.parse_args()

    # Create an instance of DataManager
    ac = initialize_db("data_and_research/db")
    data_manager = DataManager(ib_client=None,arctic=ac)
    
    if args.store_data and args.script and args.library and args.symbol:
        data_manager.store_data_from_external_scripts(args.script, args.library, args.symbol)
    
    elif args.run_script and args.script_path:
        data_manager.run_python_script(args.script_path)
    
    elif args.schedule_script and args.script_path and args.schedule_time:
        data_manager.schedule_python_script(args.script_path, args.schedule_time)
    
    else:
        print("Please provide valid arguments. Use --help for more information.")

if __name__ == "__main__":
    cwd = os.getcwd()
    base_dir = cwd.split('IB-Multi-Strategy-ATS')[0]
    data_manager_path = os.path.join(base_dir, "IB-Multi-Strategy-ATS", "data_and_research", "data_manager.py")
    print(cwd)
    main()