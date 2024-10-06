# IB_Multi_Strategy_ATS/broker/utilityfunctions.py

import requests, pytz
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import pandas_market_calendars as mcal
from zoneinfo import ZoneInfo
import yfinance as yf
import asyncio
from ib_async import *

def get_isin_from_contract(contract, ib=None):
    import xml.etree.ElementTree as ET
    if not ib:
        ib = connect_to_IB(clientid=77)
    fundamentals = ib.reqFundamentalData(contract, reportType='ReportSnapshot')
    root = ET.fromstring(fundamentals)
    for elem in root.iter():
        prev_elem = None
        for elem in root.iter():
            if prev_elem is not None:
                if prev_elem.text == contract.symbol:
                    isin = elem.text
                    return isin
            prev_elem = elem
    
def get_last_full_trading_day(current_datetime=None):
    # Create NYSE calendar
    nyse = mcal.get_calendar('NYSE')
    
    # Get NYSE timezone
    nyse_tz = pytz.timezone('America/New_York')
    
    # Use provided datetime or current time if none provided
    if current_datetime is None:
        current_datetime = datetime.now(pytz.timezone('Europe/Berlin'))
    elif current_datetime.tzinfo is None:
        current_datetime = pytz.timezone('Europe/Berlin').localize(current_datetime)
    
    # Convert to NYSE time
    nyse_time = current_datetime.astimezone(nyse_tz)
    
    # Get market schedule for the current day and the previous few days
    schedule = nyse.schedule(start_date=nyse_time.date() - timedelta(days=5), end_date=nyse_time.date())
    
    if not schedule.empty:
        # Get the last row of the schedule (should be today or the most recent trading day)
        last_day = schedule.iloc[-1]
        market_close = last_day['market_close'].tz_convert(nyse_tz)
        
        # If current time is before the market close of the last day in the schedule,
        # we need to look at the previous trading day
        if nyse_time < market_close:
            if len(schedule) > 1:
                return schedule.index[-2].date()
            else:
                # If there's only one day in the schedule, find the previous trading day
                previous_trading_days = nyse.valid_days(end_date=nyse_time.date() - timedelta(days=1), start_date=nyse_time.date() - timedelta(days=5))
                return previous_trading_days[-1].date()
        else:
            # If current time is after market close, the last day in the schedule is the last full trading day
            return last_day.name.date()
    else:
        # If there's no schedule for the recent days (e.g., long weekend), 
        # find the last trading day
        previous_trading_days = nyse.valid_days(end_date=nyse_time.date() - timedelta(days=1), start_date=nyse_time.date() - timedelta(days=5))
        return previous_trading_days[-1].date()

def get_current_or_next_trading_day(current_datetime=None):
    # Create NYSE calendar
    nyse = mcal.get_calendar('NYSE')
    
    # Get NYSE timezone
    nyse_tz = pytz.timezone('America/New_York')
    
    # Use provided datetime or current time if none provided
    if current_datetime is None:
        current_datetime = datetime.now(pytz.timezone('Europe/Berlin'))
    elif current_datetime.tzinfo is None:
        current_datetime = pytz.timezone('Europe/Berlin').localize(current_datetime)
    
    # Convert to NYSE time
    nyse_time = current_datetime.astimezone(nyse_tz)
    
    # Get market schedule for today and the next few days
    schedule = nyse.schedule(start_date=nyse_time.date(), end_date=nyse_time.date() + timedelta(days=10))
    
    if not schedule.empty:
        today_schedule = schedule.loc[schedule.index.date == nyse_time.date()]
        if not today_schedule.empty:
            market_open = today_schedule.iloc[0]['market_open'].tz_convert(nyse_tz)
            market_close = today_schedule.iloc[0]['market_close'].tz_convert(nyse_tz)
            
            # If the current time is before market close, return today
            if nyse_time <= market_close:
                return nyse_time.date()
    
    # If we're here, it means today is not a trading day or the market has closed
    # Find the next trading day
    next_trading_days = nyse.valid_days(start_date=nyse_time.date() + timedelta(days=1), end_date=nyse_time.date() + timedelta(days=10))
    return next_trading_days[0].date()

def get_earnings():
    # Get the last full trading day and the current or next trading day
    last_trading_day = get_last_full_trading_day()
    next_trading_day = get_current_or_next_trading_day()

    # Define the SQL query with the specific dates and conditions
    query = f"""
    WITH LatestEarnings AS (
        SELECT *,
            ROW_NUMBER() OVER (PARTITION BY act_symbol ORDER BY `date` DESC) AS rn
        FROM `earnings_calendar`
        WHERE `when` IS NOT NULL
    )
    SELECT *
    FROM LatestEarnings
    WHERE rn = 1
    AND (
        (`date` = '{last_trading_day}' AND `when` = 'After market close') OR
        (`date` = '{next_trading_day}' AND `when` = 'Before market open')
    )
    ORDER BY `act_symbol` ASC;
    """
    
    # URL encode the query
    encoded_query = requests.utils.quote(query)
    
    # Set the DoltHub API endpoint and parameters
    endpoint = f"https://www.dolthub.com/api/v1alpha1/post-no-preference/earnings/master?q={encoded_query}"
    
    # Make the API request
    response = requests.get(endpoint)
    response.raise_for_status()  # Check for errors

    # Check the content of the response
    data = response.json()

    # Handle the response and convert to a pandas DataFrame if successful
    if data.get('query_execution_status') == 'Success':
        df = pd.DataFrame(data['rows'])
        df = df.rename(columns={'act_symbol': 'symbol'})
        df = df[['symbol', 'date', 'when']]
        return df
    else:
        print(f"Query Error: {data.get('query_execution_message')}")

def get_vol_data(symbols: list[str] = None, curated = True, include_yf = True):

    # Build the query to get the max date from the volatility_history table
    query_max_date = """
    SELECT MAX(`date`) AS max_date
    FROM `volatility_history`
    """
    encoded_query_max_date = requests.utils.quote(query_max_date)
    endpoint_max_date = f"https://www.dolthub.com/api/v1alpha1/post-no-preference/options/master?q={encoded_query_max_date}"
    response_max_date = requests.get(endpoint_max_date) # Make the request to DoltHub for the max date
    response_max_date.raise_for_status()  # Check for errors

    # Convert the response to a pandas DataFrame
    data_max_date = response_max_date.json()

    # Extract the maximum date from the response
    if data_max_date.get('query_execution_status') == 'Success' and data_max_date.get('rows'):
        max_date = data_max_date['rows'][0]['max_date']
        print("Looking up vol data for:", max_date)
    else:
        print(f"Query Error: {data_max_date.get('query_execution_message')}")
        max_date = None

    if not max_date:
        return None
    
    if not symbols:
        earnings_table = get_earnings()
        symbols = earnings_table['symbol'].tolist()

    # Build the query to get the vol data for the max date
    symbols_str = ', '.join(f"'{symbol}'" for symbol in symbols)
    
    query_volatility = f"""
    SELECT *
    FROM `volatility_history`
    WHERE `date` = '{max_date}'
    AND `act_symbol` IN ({symbols_str})
    ORDER BY `act_symbol` ASC;
    """
    encoded_query_volatility = requests.utils.quote(query_volatility)
    endpoint_volatility = f"https://www.dolthub.com/api/v1alpha1/post-no-preference/options/master?q={encoded_query_volatility}"
    response_volatility = requests.get(endpoint_volatility) # Make the request to DoltHub for volatility history
    response_volatility.raise_for_status()  # Check for errors

    # Convert the response to a pandas DataFrame
    data_volatility = response_volatility.json()

    # Check and convert the response to a pandas DataFrame
    if data_volatility.get('query_execution_status') == 'RowLimit':
        if data_volatility.get('rows'):
            df_volatility = pd.DataFrame(data_volatility['rows'])
        else:
            print("No data found for the maximum date.")
    else:
        df_volatility = pd.DataFrame(data_volatility['rows'])
    
    if not curated:
        return df_volatility
    
    df_vol = df_volatility[['act_symbol', 'date', 'hv_current', 'iv_current']].astype({'hv_current': 'float','iv_current': 'float'})
    df_vol['vol_premium'] = df_vol['iv_current']/df_vol['hv_current']

    if include_yf:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=365*2)
        yf_data = yf.download(df_vol['act_symbol'].tolist(), start=start_date, end=end_date)
        
        # Extract the most recent close price for each symbol
        close_prices = yf_data['Close'].iloc[-1]
        
        # Merge the close price with df_vol
        df_vol['close'] = close_prices

    return df_vol.sort_values(by='vol_premium', ascending=False)

async def process_get_filtered_put_options(ib, symbol, max_dte=60, unfiltered=False,min_safety_margin=0.05,max_safety_margin=0):
    
    # Get the stock contract
    stock = Stock(symbol, 'SMART', 'USD')
    await ib.qualifyContractsAsync(stock)
    
    # Get the stock price
    [ticker] = await ib.reqTickersAsync(stock)
    stock_price = ticker.marketPrice()
    
    if np.isnan(stock_price):
        print(f"Unable to get market price for {symbol}")
        return None, None
    
    # Calculate strike range
    lower_strike = stock_price * (1-min_safety_margin)  
    upper_strike = stock_price * (1+max_safety_margin) 
    
    # Get option chains
    chains = await ib.reqSecDefOptParamsAsync(stock.symbol, '', stock.secType, stock.conId)
    
    # Get the chain with exchange 'SMART'
    chain = next((c for c in chains if c.exchange == 'SMART'), None)
    if not chain:
        print(f"No SMART chain found for {symbol}")
        return None, None
    
    # Get current date
    today = datetime.now().date()
    
    # Filter expirations and strikes
    valid_expirations = [exp for exp in chain.expirations 
                         if (datetime.strptime(exp, '%Y%m%d').date() - today).days <= max_dte]
    valid_strikes = [strike for strike in chain.strikes 
                     if lower_strike <= strike <= upper_strike]
    
    # Create option contracts
    contracts = [Option(symbol, exp, strike, 'P', 'SMART') 
                 for exp in valid_expirations 
                 for strike in valid_strikes]
    
    # Qualify the contracts
    contracts = await ib.qualifyContractsAsync(*contracts)
    
    # Request market data
    tickers = await ib.reqTickersAsync(*contracts)
    
    # Create DataFrame
    data = []
    for ticker in tickers:
        contract = ticker.contract
        expiration = datetime.strptime(contract.lastTradeDateOrContractMonth, '%Y%m%d').date()
        dte = (expiration - today).days
        data.append({
            'Symbol': symbol,
            'StockPrice': stock_price,
            'Strike': contract.strike,
            'Expiration': expiration,
            'DTE': dte,
            'Bid': ticker.bid,
            'BidSize': ticker.bidSize,
            'Ask': ticker.ask,
            'AskSize': ticker.askSize,
            'Contract': contract})
    
    df = pd.DataFrame(data)
    df = df.sort_values(['Expiration', 'Strike'])
    if unfiltered:
        return df
    options_df = df.copy()
    options_df['option_premium'] = options_df['Bid'] / options_df['Strike']
    options_df['annualized_premium'] = options_df['option_premium'] * (365 / options_df['DTE'])
    options_df['safety_margin'] = stock_price - options_df['Strike']
    options_df = options_df[(options_df['option_premium'] > 0.01) & (options_df['annualized_premium'] > 0.1)]
    options_df['safety_margin%'] = options_df['safety_margin'] / options_df['StockPrice']
    
    # Sort the DataFrame after creating all columns
    options_df = options_df.sort_values('safety_margin%', ascending=False)
    
    return options_df.head(10), stock_price

async def get_filtered_put_options(ib, symbols,max_dte = 60, unfiltered=False,min_safety_margin=0.05,max_safety_margin=0):
    tasks = [process_get_filtered_put_options(ib, symbol, max_dte, unfiltered,min_safety_margin) for symbol in symbols]
    results = await asyncio.gather(*tasks)

    all_options = []
    for options_df, _ in results:
        if options_df is not None and not options_df.empty:
            all_options.append(options_df)
    
    if all_options:
        return pd.concat(all_options, ignore_index=True)
    else:
        return pd.DataFrame()

def connect_to_IB(port=7497, clientid=0, symbol=None):
    util.startLoop()  # Needed in script mode
    ib = IB()
    try:
        ib.connect('127.0.0.1', port, clientId=clientid)
    except ConnectionError:
        ib = None  # Reset ib on failure
    return ib


if __name__ == "__main__":
    ib = connect_to_IB()
    vol_df = get_vol_data(curated=False, include_yf=False)
    symbols = vol_df['act_symbol'].tolist()
    options_df = asyncio.run(get_filtered_put_options(ib, symbols, max_dte=25, unfiltered=True))
    print(options_df)
    ib.disconnect()
