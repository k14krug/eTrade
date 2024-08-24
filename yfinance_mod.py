import yfinance as yf

# List of top 10 stocks in the Dow Jones Industrial Average
dow_tickers = ["AAPL", "MSFT", "JPM", "V", "PG", "JNJ", "UNH", "HD", "DIS", "VZ"]

def get_current_price(symbol):
    print(f"  get_current_price - Looking up symbol: {symbol}")
    ticker = yf.Ticker(symbol)
    todays_data = ticker.history(period='1d')
    print(f"Today's Data for {symbol}: {todays_data}")
    return todays_data

def get_latest_price(symbol):
    print(f"  get_latest_price - Looking up symbol: {symbol}")
    ticker = yf.Ticker(symbol)
    info = ticker.info

    if 'currentPrice' in info:
        print
        latest_price = info['currentPrice']
        return latest_price
    else:
        print(f"  get_latest_price - No 'regularMarketPrice' in info. Using history() to get latest price.")
        todays_data = ticker.history(period='1d')
        if not todays_data.empty:
            latest_price = todays_data['Close'].iloc[0]
            return latest_price
        else:
            return None
        
def search_key_by_keyword(data: dict, keyword: str) -> list[str]:
    
    return list(filter(lambda x: keyword in x.lower(), data.keys()))

msft = yf.Ticker("MSFT")
valid_market_keys = search_key_by_keyword(msft.info, "current")
print(valid_market_keys)

for ticker_symbol in dow_tickers:
    print(f"\nProcessing {ticker_symbol}...")
    #get_current_price(ticker_symbol)
    get_latest_price(ticker_symbol)