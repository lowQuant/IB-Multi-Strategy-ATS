# ATS/broker/broker.py
from collections import deque
from ib_insync import *
import threading, time
from gui.log import add_log, start_event

ib = None  # Global variable for the IB client

def connect_to_IB(port=7497, clientId=0):
    global ib
    util.startLoop()  # Needed in script mode
    ib = IB()
    try:
        ib.connect('127.0.0.1', port, clientId=clientId)
        add_log(f'IB Connection established with clientId={clientId}')
    except ConnectionError:
        add_log('Connection failed. Start TWS or IB Gateway and try again!')
        ib = None  # Reset ib on failure

    return ib

def disconnect_from_IB(ib):
    if ib and ib.isConnected():
        ib.disconnect()
        add_log("Disconnected from Interactive Brokers.")
        ib = None
