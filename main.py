# ATS/main.py
from gui import run_gui
from broker import connect_to_IB, disconnect_from_IB


def main():
    # Start the GUI without trying to connect to IB immediately
    run_gui()

# def main():
#     ib_client = connect_to_IB()
#     if ib_client and ib_client.isConnected():
#         run_gui()
#         disconnect_from_IB()  # Disconnect when the GUI is closed.
#     else:
#         print("Could not connect to Interactive Brokers.")

if __name__ == "__main__":
    main()

