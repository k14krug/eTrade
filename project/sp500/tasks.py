from celery import shared_task
from project.models import SP500Stock, SP500StockInfo, SP500HistData
from project.extensions import db, cache
from project.stock_data import StockData
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import logging
import pytz
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.exc import StaleDataError
from time import sleep
from market_status import get_market_status_for_today, is_market_open_for_date  # Import the market_status module

# Define the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def get_hist_data_for_symbol(symbol,stock_id,ticker):
    
    today = datetime.utcnow().date()
    #current_market_status = get_market_status_for_today()
    
    # Check if we already have up-to-date historical data
    latest_hist_data = SP500HistData.query.filter_by(stock_id=stock_id).order_by(SP500HistData.date.desc()).first()
    if latest_hist_data:
        start_date = latest_hist_data.date + timedelta(days=2)
        print(f"Latest historical data found for {symbol} - start: {start_date}")
    else:
        start_date = datetime(2020, 1, 1).date()

    end_date = today

    if start_date < today and start_date <= end_date:
        try:
            print(f"Fetching historical data for {symbol} - start: {start_date}, end: {end_date}")
            hist_data = ticker.history(start=start_date, end=end_date, interval='1d')
            if hist_data.empty:
                print(f"No historical data found for {symbol}.")
                return
            
            # Calculate moving averages
            hist_data['SMA_20'] = hist_data['Close'].rolling(window=20).mean()
            hist_data['SMA_50'] = hist_data['Close'].rolling(window=50).mean()

            for date, row in hist_data.iterrows():
                stock_data = SP500HistData(
                    stock_id=stock_id,
                    date=date.date(),
                    open_price=row['Open'],
                    high_price=row['High'],
                    low_price=row['Low'],
                    close_price=row['Close'],
                    volume=row['Volume'],
                    sma_20=0,  
                    sma_50=0   
                )
                db.session.add(stock_data)
            db.session.commit()
            print(f"Historical data for {symbol} saved successfully.")
        except Exception as e:
            db.session.rollback()
            print(f"Error fetching historical data for {symbol}: {e}")
        

@shared_task(name="update_sp500_data", bind=True, max_retries=0)
def update_sp500_data(self):
    try:
        # Always update SP500Stock and SP500StockInfo even if the market is closed
        wiki_stock_list = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]
        print(f"Updating S&P 500 data - looping through {len(wiki_stock_list)} stocks")

        # Get symbols from the current S&P 500 list
        wiki_symbols = set(wiki_stock_list['Symbol'].unique())

        # Add the symbol SPY to the list
        wiki_symbols.add('SPY')

        # Query the database to get already tracked stocks (previously part of S&P 500)
        tracked_stocks = SP500Stock.query.all()
        tracked_symbols = set([stock.symbol for stock in tracked_stocks])
        
        # Merge current S&P 500 symbols with previously tracked symbols
        all_symbols = wiki_symbols.union(tracked_symbols)

        # print the symbols that were in tracked stocks and not in wiki_symbols
        print(f"Symbols in tracked_stocks but not in wiki_symbols: {tracked_symbols - wiki_symbols}")

        
        print(f"Updating S&P 500 data - looping through {len(all_symbols)} stocks")

        # Loop through the combined symbol list
        for idx, symbol in enumerate(all_symbols):
            # print the symbol and its index in the loop
            print(f"Updating symbol: {symbol} - # {idx}")
            # If the symbol is in the current S&P 500 list, get details from sp500 DataFrame
            if symbol in wiki_symbols:
                row = wiki_stock_list.loc[wiki_stock_list['Symbol'] == symbol]
                if row.empty:
                    print(f"No data found for {symbol} in the current S&P 500 list.")
                    continue
                row = row.iloc[0]
                company = row['Security']
                sector = row['GICS Sector']
            else:
                # likely a stock that was removed from S&P 500 but was previously tracked and in SP500Stock table
                stock_record = SP500Stock.query.filter_by(symbol=symbol).first()
                company = stock_record.company_name if stock_record else "Unknown"
                sector = stock_record.sector if stock_record else "Unknown"

            # Update SP500Stock
            stock_record = SP500Stock.query.filter_by(symbol=symbol).first()
            if not stock_record:
                stock_record = SP500Stock(symbol=symbol, company_name=company, sector=sector)
                db.session.add(stock_record)
                db.session.flush()  # Flush to get the new `stock_id`
                
            # Fetch stock information from yfinance
            ticker = yf.Ticker(symbol)
            info = ticker.info
            if not info:
                print(f"No stock information found for {symbol}, possibly delisted.")
                continue

            # Update SP500StockInfo table
            stock_info = SP500StockInfo.query.filter_by(stock_id=stock_record.id).first()
            if not stock_info:
                stock_info = SP500StockInfo(stock_id=stock_record.id)

            stock_info.latest_price = info.get('currentPrice')
            stock_info.previous_day_price = info.get('previousClose')
            pe_ratio = info.get('trailingPE')
            if pe_ratio == 'Infinity' or pe_ratio is None:
                print(f"PE ratio was Infinity for {symbol}. Setting to None.")
                pe_ratio = None
            stock_info.one_year_target = info.get('targetMeanPrice')
            stock_info.fifty_two_week_low = info.get('fiftyTwoWeekLow')
            stock_info.fifty_two_week_high = info.get('fiftyTwoWeekHigh')
            stock_info.last_updated = datetime.utcnow()

            db.session.add(stock_info)
            db.session.commit()


            # Immediately check and update historical data for this symbol
            #print(f"Checking historical data for {symbol}")
            get_hist_data_for_symbol(symbol,stock_record.id,ticker)

        db.session.commit()
        return {'status': 'SP500 data updated successfully.'}

    except Exception as e:
        logger.error(f"Failed to update S&P 500 data: {e}")
        return {'status': f'Failed to update S&P 500 data: {str(e)}'}
