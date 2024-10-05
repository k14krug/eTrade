# stock_data.py
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import time

class StockData:
    @staticmethod
    def get_latest_price(symbol):
        ticker = yf.Ticker(symbol)
        info = ticker.info
        if 'currentPrice' in info:
            return info['currentPrice']
        else:
            todays_data = ticker.history(period='1d')
            if not todays_data.empty:
                return todays_data['Close'].iloc[0]
            else:
                return None

    @staticmethod
    def get_historical_price(symbol, date):
        stock = yf.Ticker(symbol)
        historical_data = stock.history(start=date, end=date + timedelta(days=1))
        if not historical_data.empty:
            return historical_data['Close'].iloc[0]
        return None

    @staticmethod
    def get_pe_ratio(symbol):
        ticker = yf.Ticker(symbol)
        return ticker.info.get('trailingPE', None)

    @staticmethod
    def get_sp500_data():
        sp500 = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]
        symbols = sp500['Symbol'].tolist()

        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)

        data = yf.download(symbols, start=start_date, end=end_date)

        table_data = []
        for symbol in symbols:
            try:
                current_price = data['Close'][symbol].iloc[-1]
                previous_price = data['Close'][symbol].iloc[0]
                gain_loss = current_price - previous_price
                gain_loss_percentage = (gain_loss / previous_price) * 100

                table_data.append({
                    'symbol': symbol,
                    'current_price': round(current_price, 2),
                    'previous_price': round(previous_price, 2),
                    'gain_loss': round(gain_loss, 2),
                    'gain_loss_percentage': round(gain_loss_percentage, 2)
                })
            except Exception as e:
                print(f"Error processing {symbol}: {str(e)}")

        return table_data
    
    @staticmethod
    def get_volatility_counts(symbol, days=30):
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        stock = yf.Ticker(symbol)
        hist = stock.history(start=start_date, end=end_date)
        
        if hist.empty:
            return 0, 0  # Return 0 for both counts if no data is available

        daily_returns = hist['Close'].pct_change()
        
        above_count = 0
        below_count = 0
        
        for i in range(1, len(daily_returns)):
            if daily_returns.iloc[i] > 0.01:  # 1% increase
                above_count += 1
            elif daily_returns.iloc[i] < -0.01:  # 1% decrease
                below_count += 1
        print(f"Symbol: {symbol}, above: {above_count}, below: {below_count}")
        return above_count, below_count
    
    @staticmethod
    def get_intraday_data(symbol, days=1):  # Add days parameter, default to 1
        # Fetch intraday data using yfinance
        ticker = yf.Ticker(symbol)

        if days == 1:
            # Fetching intraday data with 1-minute intervals for the last trading day
            intraday_data = ticker.history(period="1d", interval="1m")
        else:
            # Calculate the start date for the last 'days' business days
            end_date = datetime.now()
            business_days = pd.date_range(end=end_date, periods=days, freq='B')
            start_date = business_days[0]
            intraday_data = ticker.history(start=start_date, end=end_date, interval="1m")

        # Prepare data for JSON response
        dates = [d.strftime('%Y-%m-%d %H:%M:%S') for d in intraday_data.index]
        prices = intraday_data['Close'].tolist()
        volumes = intraday_data['Volume'].tolist()

        return {
            'dates': dates,
            'prices': prices,
            'volumes': volumes
        }
    
    @staticmethod
    def time_ago(publish_time):
        """
        Converts a Unix timestamp into a human-readable 'time ago' format, e.g., '2 days ago'.
        """
        current_time = time.time()
        time_diff = current_time - publish_time
        
        days = time_diff // (24 * 3600)
        if days >= 1:
            return f"{int(days)} days ago"
        hours = time_diff // 3600
        if hours >= 1:
            return f"{int(hours)} hours ago"
        minutes = time_diff // 60
        if minutes >= 1:
            return f"{int(minutes)} minutes ago"
        return "just now"

    @staticmethod
    def get_stock_news(symbol):
        """
        Fetches the latest news for a given stock symbol and returns a formatted list of articles.
        """
        ticker = yf.Ticker(symbol)
        stock_news = ticker.news

        # Format the stock news
        formatted_news = []
        for article in stock_news:
            formatted_article = {
                'title': article.get('title', 'No title available'),
                'link': article.get('link', '#'),
                'publisher': article.get('publisher', 'Unknown provider'),
                'thumbnail': article.get('thumbnail', {}).get('resolutions', [{}])[0].get('url', ''),
                'published_date': StockData.time_ago(article['providerPublishTime'])
            }
            formatted_news.append(formatted_article)
        
        return formatted_news