# ATS/broker/broker.py
from collections import deque
from ib_async import *
import threading, time


ib = None  # Global variable for the IB client

def connect_to_IB(port=7497, clientid=0, symbol=None):
    from gui.log import add_log, start_event
    global ib
    util.startLoop()  # Needed in script mode
    ib = IB()
    try:
        ib.connect('127.0.0.1', port, clientId=clientid)
        if not symbol:
            add_log(f'IB Connection established with clientId={clientid}')
        else:
            add_log(f'IB Connection established with clientId={clientid} [{symbol}]')
    except ConnectionError:
        add_log('Connection failed. Start TWS or IB Gateway and try again!')
        ib = None  # Reset ib on failure

    return ib

def disconnect_from_IB(ib, symbol=None):
    from gui.log import add_log, start_event
    if ib and ib.isConnected():
        if ib.client.clientId == 0:
            add_log("Disconnected from IB [StrategyManager]")
        else:
            if not symbol:
                add_log(f"Disconnected from IB [clientId {ib.client.clientId}]")
            else:
                add_log(f"Disconnected from IB [{symbol}]")
        ib.disconnect()
        ib = None

