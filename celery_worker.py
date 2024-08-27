import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, celery

@celery.task(bind=True)
def update_sp500_data_task(self, start_date):
    from stock_data import StockData
    
    with app.app_context():
        total_stocks = 505  # Approximate number of S&P 500 stocks
        for i, stock_data in enumerate(StockData.update_sp500_data_generator(start_date)):
            self.update_state(state='PROGRESS', meta={'current': i, 'total': total_stocks})
        return {'current': total_stocks, 'total': total_stocks, 'status': 'Task completed!'}