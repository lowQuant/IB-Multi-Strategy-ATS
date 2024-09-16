# ATS/main.py
import asyncio

from gui import run_gui
from broker import connect_to_IB, disconnect_from_IB

def main():
    # Start the GUI without trying to connect to IB immediately
    run_gui()


if __name__ == "__main__":
    main()

