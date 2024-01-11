import yfinance as yf
import pandas as pd
from arcticdb import Arctic, QueryBuilder
import datetime
import talib

try:
    from data_and_research import ac
    lib = ac.get_library('stocks', create_if_missing=True)
except:
    from utils import ac
    lib = ac.get_library('stocks', create_if_missing=True)


def is_last_business_day_in_df(df):
    """
    Check if the last business day is in the DataFrame's index.

    Args:
    df (pd.DataFrame): The DataFrame to check. Its index should be datetime-like.

    Returns:
    bool: True if the last business day is in the index, False otherwise.
    """
    # Ensure the DataFrame's index is a DatetimeIndex
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a DatetimeIndex")

    # Calculate the last business day
    last_business_day = datetime.today() - pd.tseries.offsets.BDay(1)
    print(last_business_day)

    # Check if the last business day is in the DataFrame's index
    return last_business_day.normalize() in df.index

