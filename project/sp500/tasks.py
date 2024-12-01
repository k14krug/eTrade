from celery import shared_task
from project.models import SP500Stock, SP500StockInfo, SP500HistData
from project.extensions import db, cache
from project.stock_data import StockData
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, date
import logging
import pytz
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.exc import StaleDataError
import time
from time import sleep
from market_status import get_market_status_for_today, is_market_open_for_date 
from project.sp500.deduplication_task import DeduplicationTask  
import finnhub
from flask import current_app
import os

# Define the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_finnhub_client():
    # Dynamically fetch the API key from the Flask application config
    api_key = current_app.config.get("FINNHUB_API_KEY", "your_default_api_key")
    return finnhub.Client(api_key=api_key)


def get_hist_data_for_symbol(symbol,stock_id,ticker):
    
    today = datetime.utcnow().date()
    #current_market_status = get_market_status_for_today()
    
    # Check if we already have up-to-date historical data
    latest_hist_data = SP500HistData.query.filter_by(stock_id=stock_id).order_by(SP500HistData.date.desc()).first()
    if latest_hist_data:
        start_date = latest_hist_data.date + timedelta(days=2)
        #print(f"Latest historical data found for {symbol} - start: {start_date}")
    else:
        start_date = datetime(2020, 1, 1).date()

    end_date = today

    if start_date < today and start_date <= end_date:
        try:
            #print(f"Fetching historical data for {symbol} - start: {start_date}, end: {end_date}")
            hist_data = ticker.history(start=start_date, end=end_date, interval='1d')
            if (hist_data.empty):
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
            #print(f"Historical data for {symbol} saved successfully.")
        except Exception as e:
            db.session.rollback()
            print(f"Error fetching historical data for {symbol}: {e}")


def get_earnings_data(ticker_symbol):
    try:
        # Fetch past quarterly periods and results
        finnhub_client = get_finnhub_client()
        company_earnings = finnhub_client.company_earnings(ticker_symbol, limit=10)

        # Fetch upcoming earnings calendar
        today = datetime.utcnow().date()
        future_range_end = today + timedelta(days=90)
        earnings_calendar = finnhub_client.earnings_calendar(
            _from=today.strftime("%Y-%m-%d"),
            to=future_range_end.strftime("%Y-%m-%d"),
            symbol=ticker_symbol,
        )

        # Identify the most recent fiscal period
        most_recent_period = max(company_earnings, key=lambda e: e["period"])
        most_recent_period_date = datetime.strptime(most_recent_period["period"], "%Y-%m-%d")
        most_recent_announcement_date = most_recent_period_date + timedelta(weeks=4)  # Approximate announcement date

        # Extract next earnings report date
        next_earnings = earnings_calendar.get("earningsCalendar", [])[0] if "earningsCalendar" in earnings_calendar else None

        # Format results
        earnings_info = {
            "most_recent_earnings_date": most_recent_period_date.date(),
            "actual_eps": most_recent_period.get("actual"),
            "estimated_eps": most_recent_period.get("estimate"),
            "next_earnings_report_date": next_earnings["date"] if next_earnings else None,
        }
        logger.info(f"Earnings data fetched for {ticker_symbol}")
        return earnings_info

    except finnhub.FinnhubAPIException as e:
        logger.error(f"API request failed for {ticker_symbol}: {e}")
        return {"message": f"Error fetching earnings data for {ticker_symbol}"}

#@shared_task(name="update_sp500_data", bind=True, max_retries=0)
@shared_task(base=DeduplicationTask, name="update_sp500_data", bind=True, max_retries=0)
def update_sp500_data(self):
    worker_name = self.request.hostname  # Get the celery worker name
    error_symbols = []  # Track symbols with errors
    try:
        # Fetch current S&P 500 data
        wiki_stock_list = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]
        wiki_symbols = set(wiki_stock_list['Symbol'].unique())
        tracked_stocks = SP500Stock.query.all()
        tracked_symbols = set(stock.symbol for stock in tracked_stocks)
        stock_dict = {stock.symbol: stock for stock in tracked_stocks}
        all_symbols = wiki_symbols.union(tracked_symbols)
        total_symbols = len(all_symbols)
        loop_status_lit = "Celery backround task updating prices and earnings data for S&P 500 stocks."

        # Step 1: Price Data
        for idx, symbol in enumerate(all_symbols):
            #logger.info(f"Processing price data for {symbol} ({idx + 1}/{len(all_symbols)})")
            try:
                update_price_data(symbol, stock_dict, wiki_stock_list)
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error updating price data for {symbol}: {e}")
                error_symbols.append(symbol)
            # Calculate progress for the first loop
            progress = ((idx + 1) / total_symbols) * 50  # First loop represents 50% of total
            self.update_state(state='PROGRESS', meta={'status': f'{loop_status_lit} Prices:{idx+1}/{total_symbols}. Total Progress {progress:.2f}% complete'})


        # Step 2: Earnings Data
        for idx, symbol in enumerate(all_symbols):
            try:
                update_earnings_data(symbol, stock_dict, idx)
                time.sleep(1)  # Throttle requests
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error updating earnings data for {symbol}: {e}")
                error_symbols.append(symbol)
                # Calculate progress for the second loop
                progress = 50 + ((idx + 1) / total_symbols) * 50  # Add 50% for second loop
                self.update_state(state='PROGRESS', meta={'status': f'{loop_status_lit} Earnings:{idx+1}/{total_symbols}. Total progress {progress:.2f}% complete'})


        db.session.commit()
        if error_symbols:
            logger.error(f"Symbols with errors: {', '.join(error_symbols)}")
        return {'status': 'SP500 data updated successfully.'}
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to update SP500 data: {e}")
        return {'status': f'Failed to update SP500 data: {str(e)}'}
    
def update_price_data(symbol, stock_dict, wiki_stock_list):
    # Get or create stock_record
    stock_record = stock_dict.get(symbol)
    if not stock_record:
        # Add new stock if not tracked previously
        row = wiki_stock_list.loc[wiki_stock_list['Symbol'] == symbol]
        company = row.iloc[0]['Security'] if not row.empty else "Unknown"
        sector = row.iloc[0]['GICS Sector'] if not row.empty else "Unknown"
        stock_record = SP500Stock(symbol=symbol, company_name=company, sector=sector)
        db.session.add(stock_record)
        db.session.flush()  # Flush to generate ID
        stock_dict[symbol] = stock_record  # Update local cache

    # Fetch stock data from yfinance
    ticker = yf.Ticker(symbol)
    info = ticker.info
    if not info:
        logger.warning(f"No stock information found for {symbol}.")
        return

    # Fetch or create SP500StockInfo record
    stock_info = SP500StockInfo.query.filter_by(stock_id=stock_record.id).first()
    if not stock_info:
        stock_info = SP500StockInfo(stock_id=stock_record.id)
        db.session.add(stock_info)

    # Update stock info fields
    stock_info.latest_price = info.get('currentPrice')
    stock_info.previous_day_price = info.get('previousClose')
    stock_info.one_year_target = info.get('targetMeanPrice')
    stock_info.fifty_two_week_low = info.get('fiftyTwoWeekLow')
    stock_info.fifty_two_week_high = info.get('fiftyTwoWeekHigh')
    stock_info.last_updated = datetime.utcnow()

    # Commit changes
    db.session.add(stock_info)
    db.session.commit()
def update_earnings_data(symbol, stock_dict, idx):
    # Get stock record
    stock_record = stock_dict.get(symbol)
    logger.info(f"Processing earnings data for {symbol} ({idx + 1}/{len(stock_dict)}) {stock_record.company_name}, {stock_record.sector}")
            
    if not stock_record:
        logger.warning(f"Stock record not found for {symbol}. Skipping earnings update.")
        return
    
    # Skip if the stock represents an index (company_name equals sector)
    if stock_record.company_name == stock_record.sector:
        logger.info(f"Skipping earnings update for index: {symbol} ({stock_record.company_name})")
        return

    # Check if earnings data needs updating
    now = datetime.utcnow()
    if stock_record.most_recent_eps_date:
        last_earnings_date = stock_record.most_recent_eps_date
        if isinstance(last_earnings_date, date) and not isinstance(last_earnings_date, datetime):
            last_earnings_date = datetime.combine(last_earnings_date, datetime.min.time())
        if last_earnings_date and (now - last_earnings_date).days <= 60:
            #logger.info(f"Earnings data is up-to-date for {symbol}. Skipping update.")
            return

    # Fetch earnings data from Finnhub
    earnings_data = get_earnings_data(symbol)
    if earnings_data:
        stock_record.next_eps_date = earnings_data.get('next_earnings_report_date')
        stock_record.most_recent_eps_date = earnings_data.get('most_recent_earnings_date')
        stock_record.actual_eps = earnings_data.get('actual_eps')
        stock_record.estimated_eps = earnings_data.get('estimated_eps')
        db.session.add(stock_record)
    db.session.commit()
