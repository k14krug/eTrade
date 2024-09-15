# sp500_hist_initializer.py

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from project.models import SP500Stock, SP500HistData
from project.extensions import db
from sqlalchemy.exc import IntegrityError
import logging
import sys
import os
from project import create_app  # Adjust this import based on your app setup


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_sp500_data(start_date=None):
    print("Start of Initializing S&P 500 data")
    if start_date is None:
        start_date = datetime.now() - timedelta(days=365*5)  # Default to 5 years of data

    print(f"  Start date: {start_date}")
    # Fetch the list of S&P 500 companies
    sp500 = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]
    
    for _, row in sp500.iterrows():
        symbol = row['Symbol']
        company_name = row['Security']
        sector = row['GICS Sector']

        logger.info(f"Processing {symbol} - {company_name}")

        # Create or update the SP500Stock entry
        stock = SP500Stock.query.filter_by(symbol=symbol).first()
        if not stock:
            stock = SP500Stock(symbol=symbol, company_name=company_name, sector=sector)
            db.session.add(stock)
            try:
                db.session.commit()
            except IntegrityError:
                logger.warning(f"Stock {symbol} already exists. Skipping creation.")
                db.session.rollback()
                stock = SP500Stock.query.filter_by(symbol=symbol).first()

        # Fetch historical data
        ticker = yf.Ticker(symbol)
        hist = ticker.history(start=start_date)

        for date, row in hist.iterrows():
            stock_data = SP500HistData(
                stock_id=stock.id,
                date=date.date(),
                open_price=row['Open'],
                high_price=row['High'],
                low_price=row['Low'],
                close_price=row['Close'],
                volume=row['Volume']
            )
            db.session.add(stock_data)

        try:
            db.session.commit()
            logger.info(f"Historical data added for {symbol}")
        except IntegrityError:
            logger.warning(f"Some historical data for {symbol} already exists. Skipping duplicates.")
            db.session.rollback()

    logger.info("S&P 500 initialization complete")

if __name__ == "__main__":
    print("In Main - Initializing S&P 500 data")
    app, _ = create_app()  # Unpack the app and ignore the celery instance
    with app.app_context():  # Enter the application context
        initialize_sp500_data()  # Call your initialization function