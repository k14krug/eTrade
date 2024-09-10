from celery import shared_task
from .models import SP500Stock, SP500StockInfo
from .extensions import db, cache
import pandas as pd
import yfinance as yf
from datetime import datetime
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