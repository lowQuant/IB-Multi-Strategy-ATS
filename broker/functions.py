# IB-MULTI-STRATEGY-ATS/broker/functions.py
import numpy as np
import pandas as pd
import yfinance as yf
from ib_insync import *
# from gui.log import add_log
import datetime

# util.startLoop()  # Needed in script mode
# ib = IB()
# try:
#     ib.connect('127.0.0.1', 7497, clientId=2)
# except ConnectionError:
#     print('Connection failed. Start TWS or IB Gateway and try again!')
# except:
#     ib.connect('127.0.0.1', 7497, clientId=4)


######## FUNCTIONS TO RETRIEVE INSTRUMENT QUOTES
def get_term_structure(future_symbol,index_symbol, exchange=None, yf = False, ib=None):
        """Returns a DataFrame of a futures term structure

        param future_symbol str:    contract's ib ticker symbol
        param index_symbol  str:    Index symbol
        param yf            bool:   index_symbol can be yfinance index symbol if yf=True
        """
        today = datetime.datetime.now()

        # Generate contract months for the next 9 maturities
        monthly_expirations = [
            f"{today.year + (today.month + i - 1) // 12}{(today.month + i - 1) % 12 + 1:02}" 
            for i in range(13)
        ]
        
        # Create Future objects for each contract month
        
        if exchange is None:
            contracts = [Future(future_symbol, lastTradeDateOrContractMonth=exp) for exp in monthly_expirations]
            qualified_contracts = ib.qualifyContracts(*contracts)
        else:
            try:
                contracts = [Future(symbol=future_symbol, exchange=exchange,lastTradeDateOrContractMonth=exp) for exp in monthly_expirations]
                qualified_contracts = ib.qualifyContracts(*contracts)
            except:
                contracts = [Future(symbol=future_symbol, exchange=exchange, lastTradeDateOrContractMonth=exp) 
                            for exp in monthly_expirations if exp[-1] in ['3','6','9','12']]
                qualified_contracts = ib.qualifyContracts(*contracts)
        ib.sleep(1)

        # Set market data type to delayed frozen data
        ib.reqMarketDataType(3)

        if yf:
            spot = get_index_spot(index_symbol)
            # Prepare data collection
        else:
            idx = Index(index_symbol)
            ib.qualifyContracts(idx)
            idx_details = ib.reqMktData(idx)
            ib.sleep(2)
            spot = idx_details.last

        futures_data = {
            'Contract': ["Index"] + [contract.localSymbol for contract in qualified_contracts],
            'LastPrice': [spot],
            'DTE': [0],
            'AnnualizedYield': [None]
        }

        for contract in qualified_contracts:
            market_data = ib.reqMktData(contract)
            ib.sleep(1)  # Wait for the data to be fetched
            last_price = market_data.last if market_data.last > 0 else market_data.bid

            expiration_date = datetime.datetime.strptime(contract.lastTradeDateOrContractMonth, '%Y%m%d')
            dte = (expiration_date - today).days
            annualized_yield = None

            if dte != 0:
                annualized_yield = ((last_price / spot) ** (365 / dte) - 1) if last_price <= spot else ((spot / last_price) ** (365 / dte) - 1)

            futures_data['LastPrice'].append(last_price)
            futures_data['DTE'].append(dte)
            futures_data['AnnualizedYield'].append(annualized_yield)

        # Convert the dictionary to DataFrame
        term_structure = pd.DataFrame(futures_data)
        return term_structure
        
def get_index_spot(yf_ticker):
# Fetch data for the VIX index
    idx = yf.Ticker(yf_ticker)

    # Get the current price
    current_price = idx.info#['regularMarketPrice']
    try:
        if 'regularMarketPrice' in idx.info.keys():
            spot = idx.info['regularMarketPrice']
        else:
            spot = idx.info['regularMarketPreviousClose']
        return spot
    except Exception as e:
         print(f"Error: {e}")
    #print(f"Current VIX index price: {current_price}")

# spot = get_index_spot("^VIX")


# df = get_term_structure("ES","SPX","CME")
# print(df)
# df = get_term_structure("VXM","VIX")
# print(df)

