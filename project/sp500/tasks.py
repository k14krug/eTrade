from celery import shared_task
from project.models import SP500Stock, SP500StockInfo, SP500HistData
from project.extensions import db, cache
from project.stock_data import StockData
import pandas as pd
import yfinance as yf
from datetime import datetime, date
import logging
from celery.contrib.abortable import AbortableTask


logger = logging.getLogger(__name__)

@shared_task(name="update_sp500_data", bind=True)
def update_sp500_data(self):
    try:
        sp500 = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]
        logger.info(f"Updating S&P data - looping through {len(sp500)} stocks")
        for _, row in sp500.iterrows():
            symbol = row['Symbol']
            #print(f"Processing symbol {symbol}")
            #db.session.add(SP500Stock(name=form_data['name']))
            #db.session.commit()
            stock = SP500Stock.query.filter_by(symbol=symbol).first()

            if not stock:
                stock = SP500Stock(symbol=symbol, company_name=row['Security'], sector=row['GICS Sector'])
                db.session.add(stock)

            ticker = yf.Ticker(symbol)
            info = ticker.info

            stock_info = SP500StockInfo.query.filter_by(stock_id=stock.id).first()
            if not stock_info:
                stock_info = SP500StockInfo(stock_id=stock.id)

            stock_info.latest_price = info.get('currentPrice')
            stock_info.previous_day_price = info.get('previousClose')
            stock_info.pe_ratio = info.get('trailingPE')
            stock_info.one_year_target = info.get('targetMeanPrice')
            stock_info.fifty_two_week_low = info.get('fiftyTwoWeekLow')
            stock_info.fifty_two_week_high = info.get('fiftyTwoWeekHigh')
            times_above, times_below = StockData.get_volatility_counts(symbol)
            stock_info.times_above_one_percent = times_above
            stock_info.times_below_one_percent = times_below
            
            stock_info.last_updated = datetime.utcnow()

            #print(f"Adding stock_info for {symbol}, last_updated: {stock_info.last_updated}")    
            db.session.add(stock_info)
            
            self.update_state(state='PROGRESS', meta={'status': f'Processed {symbol}'})
            #print(f"Completed symbol {symbol}, last_updated: {stock_info.last_updated}")

        db.session.commit()
        print(f"final commit of all stocks done")
        cache.set('sp500_last_updated', datetime.utcnow())
        return {'status': 'Task completed successfully'}
    except Exception as e:
        logger.error(f"Error in update_sp500_data: {str(e)}")
        raise self.retry(exc=e)
    
@shared_task(name="update_sp500_hist_data", bind=True)
def update_sp500_hist_data(self, symbol="NVDA", start_date=date(2024, 1, 1)):
    try:
        stock = SP500Stock.query.filter_by(symbol=symbol).first()
        if not stock:
            return {'status': f'Stock {symbol} not found'}

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

        db.session.commit()
        return {'status': f'Historical data updated for {symbol}'}
    except Exception as e:
        return {'status': f'Error updating historical data for {symbol}: {str(e)}'}