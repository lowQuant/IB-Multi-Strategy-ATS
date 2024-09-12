import numpy as np
import pandas as pd
import yfinance as yf
import time, datetime
from arcticdb import QueryBuilder
import yfinance as yf
import talib
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import ac, initialize_db

ac = initialize_db('data_and_research/db')
universe = ac.get_library('univ', create_if_missing=True)
df = universe.read('us_equities',columns=['Symbol','Name','Sector','Market Cap']).data

symbols = df['Symbol'].unique().to_list()
names = df.Name.to_list()
sectors = df.Sector.to_list()

lib = ac.get_library('us_equities', create_if_missing=True)

# Alternative Idea - due to large universe 
# 1) split symbols by sector
# 2) calculate sector ranks
# 3) Store each sector group in a sector table in ArcticDB, e.g. us_equities/sectorname
# 4) Store each stock individually in us_equities/symbol
# 5) Create a sector overview table in ArcticDB that tracks relative strength of sectors (short-term) and (long-term) - ArcticDBs aggregate function can help

def split_symbols(symbols, chunk_size):
    """Split a list of symbols into smaller chunks."""
    for i in range(0, len(symbols), chunk_size):
        yield symbols[i:i + chunk_size]

# Example usage
chunked_symbols = list(split_symbols(symbols, 2))
print(f"Splitting symbols into {len(chunked_symbols)} chunks.")

# Function to download and store data
def download_and_store(chunk):
    data = yf.download(chunk, group_by="Ticker", period="3y", auto_adjust=True)
    print(data.head())
    df = data.stack(level=0).rename_axis(['Date', 'Symbol']).reset_index(level=1)
    df = df.sort_values(by='Symbol',axis='index',kind='stable')
    print(df.columns)
    # Add additional information
    df["Name"] = df["Symbol"].map(symbol_df["Name"])
    df['Sector'] = df['Symbol'].map(symbol_df['Sector'])

    df["20D_SMA"] = df.groupby("Symbol")["Close"].rolling(window=20).mean().reset_index(level=0, drop=True)
    df["50D_SMA"] = df.groupby("Symbol")["Close"].rolling(window=50).mean().reset_index(level=0, drop=True)
    df["200D_SMA"] = df.groupby("Symbol")["Close"].rolling(window=200).mean().reset_index(level=0, drop=True)
    #df['ATR'] = df.groupby('Symbol').apply(lambda group: talib.ATR(group['High'], group['Low'], group['Close'], timeperiod=14)).reset_index(level=0, drop=True)
    print(df)
    df['1M'] = df.groupby('Symbol')['Close'].pct_change(21)
    df['3M'] = df.groupby('Symbol')['Close'].pct_change(63)
    df['6M'] = df.groupby('Symbol')['Close'].pct_change(126)
    df['12M'] = df.groupby('Symbol')['Close'].pct_change(252)
    df['RS IBD'] = 2*df['3M']+df['6M']+df['12M'] # IBD Relative Strength =  2x 3M + 1x 6M + 1x 12M
    df['RS Rank'] = df.groupby(df.index)['RS IBD'].rank(pct=True)
    df["RS Rank 20D MA"] = df.groupby("Symbol")["RS Rank"].rolling(window=20).mean().reset_index(level=0, drop=True)

    for symbol in df.Symbol.unique().tolist():
        stock_data = df[df['Symbol']==symbol]
        # Store in Arctic
        print(f"saving {symbol} to arcticdb")
        lib.write(symbol, stock_data)

# Download and store data for each chunk
for chunk in chunked_symbols[:2]:
    download_and_store(chunk)