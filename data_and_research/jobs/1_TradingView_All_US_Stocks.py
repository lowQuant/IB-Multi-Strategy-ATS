# This script scrapes the TradingView website and saves all active US stocks in a .csv-file

import asyncio
from playwright.async_api import async_playwright
import pandas as pd
from tqdm.asyncio import tqdm
import numpy as np
import datetime

# Helper functions for data cleaning
def clean_market_cap_and_price(value):
    value = value.replace(",","")
    try:
        if "B" in value:
            return float(value.replace("B", "").replace("USD", "").strip()) * 1e9
        elif "M" in value:
            return float(value.replace("M", "").replace("USD", "").strip()) * 1e6
        elif "K" in value:
            return float(value.replace("K", "").replace("USD", "").strip()) * 1e3
        elif "T" in value:
            return float(value.replace("T", "").replace("USD", "").strip()) * 1e12
        elif " USD" in value:
            return float(value.replace(" USD",""))
        else:
            return np.nan  # Handle unexpected formats
    except:
        return np.nan

def clean_volume(value):
    try:
        if "M" in value:
            return float(value.replace("M", "").strip()) * 1e6
        elif "K" in value:
            return float(value.replace("K", "").strip()) * 1e3
        else:
            return np.nan  # Handle unexpected formats
    except:
        return np.nan

async def scrape_data():
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=False)
        page = await browser.new_page()

        # Load page
        await page.goto("https://www.tradingview.com/markets/stocks-usa/market-movers-all-stocks/")
        
        # Click 'Load More' until no more button is found
        while True:
            try:
                load_more_btn = await page.wait_for_selector('span.content-D4RPB3ZC', timeout=10000)
                await load_more_btn.click()
            except Exception as e:
                print("No more 'Load More' buttons or error occurred:", e)
                break
        
        # Get all row elements
        tr_elements = await page.query_selector_all('tr.row-RdUXZpkv.listRow')

        data = []
        print("Number of rows found: ", len(tr_elements))

        # Process each row
        async for row in tqdm(tr_elements, desc="Processing rows", unit="row"):
            cols = await row.query_selector_all("td")
            if cols:  # Skip empty rows
                row_data = []

                # Extract the symbol and company name from the first column
                ticker_link = await cols[0].query_selector('a.tickerNameBox-GrtoTeat')
                if ticker_link:
                    symbol = await ticker_link.inner_text()
                    name = await ticker_link.get_attribute('title')
                    name = name.split(' − ', 1)[-1].rstrip('D').strip()  # Extract company name
                    row_data.append(symbol)
                    row_data.append(name)
                
                # Extract remaining columns (Price, Change %, Volume, etc.)
                for i, col in enumerate(cols[1:], start=1):
                    text = await col.inner_text()
                    row_data.append(text)

                # Add row data to the list
                data.append(row_data)
        
        # Define column headers
        headers = ["Symbol", "Name", "Price", "Change %", "Volume", "Rel Volume", "Market Cap",
                   "P/E", "EPS (dil TTM)", "EPS Growth (TTM YoY)", "Div Yield % TTM", "Sector", "Analyst Rating"]
        
        # Convert to DataFrame
        df = pd.DataFrame(data, columns=headers)

        # Clean Price, Market Cap and Volume columns
        df['Price'] = df['Price'].apply(clean_market_cap_and_price)
        df['Market Cap'] = df['Market Cap'].apply(clean_market_cap_and_price)
        df['Volume'] = df['Volume'].apply(clean_volume)

        # Save cleaned data to CSV
        df.to_csv("univ_us_equities.csv")
        
        # Optionally close the browser
        await browser.close()
        
        return df

def main():
    print(f"Start: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    df = asyncio.run(scrape_data())
    print(f"End: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return df
    
if __name__ == "__main__":
    main()