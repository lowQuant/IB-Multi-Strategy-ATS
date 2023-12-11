
# gui/utils.py
import threading, webbrowser, subprocess, requests
import os, time
import importlib.util
from broker import connect_to_IB, disconnect_from_IB
from strategy_manager import StrategyManager
from .log import add_log, start_event

# ... other imports ...

# Global variables for strategy threads
strategy_threads = []
jupyter_subprocess = None


# consider deleting
def load_strategy(strategy_name):
    """
    Dynamically load a strategy module given the strategy file name.
    """
    strategy_module = None
    module_path = f"strategy_manager/strategies/{strategy_name}.py"
    module_name = strategy_name

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec and spec.loader:
        strategy_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(strategy_module)
    return strategy_module


def start_trading(stop_button, start_button, window, start_event):
    global strategy_manager
    ib_client = connect_to_IB()
    if ib_client:
        start_event.set()
        add_log("Connected to Interactive Brokers.")
        # strategy_manager = StrategyManager(ib_client)
        # strategy_manager.start_all()
        global strategy_threads
        strategies = [f[:-3] for f in os.listdir("strategy_manager/strategies") if f.endswith('.py') and 'strategy' in f]
        for strategy_name in strategies:
            strategy_module = load_strategy(strategy_name)
            if strategy_module and hasattr(strategy_module, 'run'):
                t = threading.Thread(target=strategy_module.run,args=(ib_client,))# start_event,))
                t.daemon = True
                t.start()
                strategy_threads.append(t)

        stop_button.place(x=48.0, y=79.0, width=178.0, height=58.0)  # Show 'Stop Trading' button
        start_button.place_forget()  # Hide 'Start Trading' button
        window.update_idletasks()  # Update the window to reflect changes
    else:
        # If connection fails, update the log
        add_log("Failed to connect to Interactive Brokers.")
        # update_log_message(canvas, log_text_item, "Failed to connect to Interactive Brokers.")


def stop_trading(stop_button, start_button, window):
    # global strategy_manager
    # if strategy_manager:
    #     start_event.clear()
    #     disconnect_from_IB()
    #     # strategy_manager.stop_all()
    
    global strategy_threads
    start_event.clear()  # Signal to threads to stop
    time.sleep(6)
    add_log("Disconnected from Interactive Brokers.")
    
    start_button.place(x=48.0, y=79.0, width=178.0, height=58.0)  # Show 'Start Trading' button
    stop_button.place_forget()  # Hide 'Stop Trading' button
    window.update_idletasks()  # Update the window to reflect changes

    # for thread in strategy_threads:
    #     if thread.is_alive():
    #         thread.join(timeout=5)  # Wait for the thread to finish


def exit_application(window):
    print("Terminating Jupyter Process")
    terminate_jupyter_server()

    print("Exiting Application")
    window.quit()  # This will quit the Tkinter mainloop

def update_log_message(canvas, log_text_item, message: str):
    """ Append message to the canvas text item, keeping only the last 10 messages. """
    current_text = canvas.itemcget(log_text_item, 'text')
    lines = current_text.split('\n')
    lines.append(message)  # Add the new message
    # Keep only the last 10 lines
    lines = lines[-10:]
    new_text = "\n".join(lines)
    canvas.itemconfigure(log_text_item, text=new_text)  # Update the canvas text item

def launch_jupyter(event=None):
    # Start Jupyter in a new thread
    jupyter_thread = threading.Thread(target=start_jupyter_server)
    jupyter_thread.start()

    # Wait for the Jupyter server to be ready
    while not is_jupyter_running():
        time.sleep(1)

    # Launch the browser with the Jupyter URL
    webbrowser.open("http://localhost:8888/tree/data_and_research")


def start_jupyter_server():
    global jupyter_subprocess
    jupyter_subprocess = subprocess.Popen(["jupyter", "notebook", "--no-browser"])
    

def is_jupyter_running():
    try:
        response = requests.get("http://localhost:8888")
        return response.status_code == 200
    except requests.ConnectionError:
        return False

def terminate_jupyter_server():
    global jupyter_subprocess
    print(jupyter_subprocess)
    if jupyter_subprocess:
        # Politely ask the subprocess to terminate
        jupyter_subprocess.terminate()
        print("after termination:", jupyter_subprocess)
        # Wait a moment for the process to terminate
        time.sleep(2)
        if jupyter_subprocess.poll() is None:  # Check if the process is still running
            # Forcefully kill the process
            print("Using kill to end jupyter server")
            jupyter_subprocess.kill()
        jupyter_subprocess = None