from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import pandas as pd

class TradingViewSymbols(webdriver.Firefox):
    '''A Class to control a browser and scrape TradingView symbols'''

    def __init__(self, service=FirefoxService(GeckoDriverManager().install()), teardown=True):
        self.service = service
        self.teardown = teardown
        super(TradingViewSymbols, self).__init__(service=self.service)
        self.implicitly_wait(10)
        self.maximize_window()

    def __exit__(self, *args) -> None:
        if self.teardown:
            self.quit()
            return super().__exit__(*args)

    def load_page(self):
        self.get("https://www.tradingview.com/markets/stocks-usa/market-movers-all-stocks/")

    def click_load_more(self):
        try:
            while True:
                load_more_btn = WebDriverWait(self, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'span[class="content-D4RPB3ZC"]'))
                )
                load_more_btn.click()
        except (NoSuchElementException, TimeoutException):
            print("No more 'Load More' buttons to click or button not found.")

    def scrape_data(self):
        self.load_page()
        self.click_load_more()
        
        # get table element
        table = self.find_element(By.CSS_SELECTOR,'table[class="table-Ngq2xrcG"]')

        # extract headers
        headers = [header.text.split('\n')[0] for header in table.find_elements(By.CSS_SELECTOR, "th")]
        headers.insert(1,'Name')
        print(f"Extracting table with headers: {headers}")
        
        # extract data
        rows = table.find_elements(By.CSS_SELECTOR, "tr")
        data = []
        for row in rows:
            cols = row.find_elements(By.CSS_SELECTOR, "td")  # or 'th' if the table has headers inside rows
            if cols:  # This skips the header row
                row_data = []
                for i, col in enumerate(cols):
                    if i == 0:  # This is the first column with symbol and company name
                        parts = col.text.split('\n')
                        symbol = parts[0]
                        name = parts[1].rstrip('D').strip()  # Remove trailing 'D' and any whitespace
                        row_data.append(symbol)
                        row_data.append(name)
                    else:
                        row_data.append(col.text)
                data.append(row_data)

        self.df = pd.DataFrame(data, columns=headers)
        self.df.to_csv("symbols.csv",header=0)
        return self.df


if __name__ == '__main__':
    TradingViewBot = TradingViewSymbols()
    df = TradingViewBot.scrape_data()
    TradingViewBot.quit()