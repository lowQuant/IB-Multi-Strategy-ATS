import numpy as np
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import datetime
from data_and_research import ac
import arcticdb as adb
import talib
from tqdm import tqdm 

import warnings

# Suppress specific FutureWarnings
warnings.filterwarnings("ignore", category=FutureWarning)

univ = ac.get_library('univ', create_if_missing=True)
univ_df = univ.read('us_equities',columns=['Symbol','Name','Sector','Market Cap']).data

sector_lib = ac.get_library('us_sectors', create_if_missing=True)
stock_lib = ac.get_library('us_equities', create_if_missing=True)

# Create a dictionary mapping Symbols to Columns we want to keep
symbol_to_name = dict(zip(univ_df["Symbol"], univ_df["Name"]))
symbol_to_sector = dict(zip(univ_df["Symbol"], univ_df["Sector"]))
symbol_to_mktcap = dict(zip(univ_df["Symbol"], univ_df["Market Cap"]))

for sector in univ_df['Sector'].unique().tolist():
    print(f'{datetime.datetime.now()}: Downloading {sector} data')
    sdf = univ_df[univ_df.Sector == sector]
    sector_symbols = sdf.Symbol.to_list()

    if len(stock_lib.list_symbols()) == 0:
        data = yf.download(sector_symbols, group_by="Ticker", period="max", auto_adjust=True)
    else:
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=560)  # Approximately 1.5 years
        data = yf.download(sector_symbols, group_by="Ticker", start=start_date, end=end_date, auto_adjust=True)

    print(f'{datetime.datetime.now()}: {sector} data downloaded. Continue with ind calcs.')
    df = data.stack(level=0).rename_axis(['Date', 'Symbol']).reset_index(level=1)
    df = df.sort_values(by='Symbol',axis='index',kind='stable')

    # Insert Name, Sector, MktCap columns
    df["Name"] = df["Symbol"].map(symbol_to_name)
    df['Sector'] = df['Symbol'].map(symbol_to_sector)
    df['Market Cap'] = df['Symbol'].map(symbol_to_mktcap)

    # Calculating technical indicators
    df['1M'] = df.groupby('Symbol')['Close'].pct_change(21)
    df['3M'] = df.groupby('Symbol')['Close'].pct_change(63)
    df['6M'] = df.groupby('Symbol')['Close'].pct_change(126)
    df['12M'] = df.groupby('Symbol')['Close'].pct_change(252)
    df['RS IBD'] = 2*df['3M']+df['6M']+df['12M'] # IBD Relative Strength =  2x 3M + 1x 6M + 1x 12M
    df['RS Rank'] = df.groupby(df.index)['RS IBD'].rank(pct=True)
    df["RS Rank 20D MA"] = df.groupby("Symbol")["RS Rank"].rolling(window=20).mean().reset_index(level=0, drop=True)

    # Calculate EMAs
    df["20D_EMA"] = df.groupby("Symbol")["Close"].transform(lambda x: ta.ema(x, length=20))
    df["50D_EMA"] = df.groupby("Symbol")["Close"].transform(lambda x: ta.ema(x, length=50))
    df["200D_EMA"] = df.groupby("Symbol")["Close"].transform(lambda x: ta.ema(x, length=200))

    df['ATR'] = df.groupby('Symbol').apply(lambda group: talib.ATR(group['High'], group['Low'], group['Close'], timeperiod=20)).reset_index(level=0, drop=True)
    df['STD'] = df.groupby('Symbol')['Close'].rolling(window=20).std().reset_index(level=0, drop=True)

    df['KC_Upper'] = df.groupby('Symbol').apply(lambda x: x['20D_EMA'] + (x['ATR'] * 1.5)).shift(1).reset_index(level=0, drop=True)  # Upper Keltner Channel
    df['KC_Lower'] = df.groupby('Symbol').apply(lambda x: x['20D_EMA'] - (x['ATR'] * 1.5)).shift(1).reset_index(level=0, drop=True)  # Lower Keltner Channel

    df['DC_Upper'] = df.groupby('Symbol')['High'].rolling(window=20).max().shift(1).reset_index(level=0, drop=True)  # Upper Donchian Channel
    df['DC_Lower'] = df.groupby('Symbol')['Low'].rolling(window=20).min().shift(1).reset_index(level=0, drop=True)  # Lower Donchian Channel

    df['BB_Upper'] = df.groupby('Symbol').apply(lambda x: x['20D_EMA'] + (x['STD'] * 2)).shift(1).reset_index(level=0, drop=True) # Upper Bollinger Band
    df['BB_Lower'] = df.groupby('Symbol').apply(lambda x: x['20D_EMA'] - (x['STD'] * 2)).shift(1).reset_index(level=0, drop=True) # Lower Bollinger Band

    # Daily Returns for later aggregation & comparing among sectors
    # df['log_ret_1d'] = df.groupby('Symbol')['Close'].apply(lambda x: np.log(x.shift(-1) / x))
    df['1d'] = df.groupby('Symbol')['Close'].pct_change(1)

    df.sort_index(inplace=True)

    # Store the data in ArcticDB
    print(f'{datetime.datetime.now()}: Writing {sector} data to ArcticDB')
    sector_lib.write(f'{sector}', df)
    print(f'{datetime.datetime.now()}: {sector} data written to ArcticDB')

    # # Store each symbol individually
    # for symbol in tqdm(sector_symbols):
    #     symbol_data = df[df.Symbol == symbol]
    #     stock_lib.write(f'{symbol}', symbol_data)

    
    # Store each symbol individually using batch writing
    payloads = []  # Create a list to store WritePayload objects
    for symbol in tqdm(sector_symbols):  # Wrap the loop with tqdm
        symbol_data = df[df.Symbol == symbol]
        payload = adb.WritePayload(symbol, symbol_data)
        payloads.append(payload)
    
    # Write the batch
    items = stock_lib.write_batch(payloads)
    print(f'{datetime.datetime.now()}: Batch write completed for {sector}')
