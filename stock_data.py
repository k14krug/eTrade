# Description: This file contains the StockData class which is responsible for fetching stock data from Yahoo Finance
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
from models import db, SP500Stock, SP500DailyData, SP500MonthlyStats
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

class StockData:

    def update_sp500_data_generator(start_date):
        sp500 = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]
        
        for _, row in sp500.iterrows():
            symbol = row['Symbol']
            name = row['Security']
            sector = row['GICS Sector']
            
            stock = SP500Stock.query.filter_by(symbol=symbol).first()
            if not stock:
                stock = SP500Stock(symbol=symbol, name=name, sector=sector)
                db.session.add(stock)
                try:
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    continue
            
            stock_info = StockData.get_stock_info(symbol)
            
            stock.current_pe = stock_info['current_pe']
            stock.one_year_target = stock_info['one_year_target']
            stock.earnings_date = stock_info['earnings_date']
            stock.fifty_two_week_low = stock_info['fifty_two_week_low']
            stock.fifty_two_week_high = stock_info['fifty_two_week_high']
            stock.last_updated = datetime.utcnow()
            
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_date)
            
            for date, data in hist.iterrows():
                existing_data = SP500DailyData.query.filter_by(stock_id=stock.id, date=date.date()).first()
                if existing_data:
                    existing_data.open_price = data['Open']
                    existing_data.high_price = data['High']
                    existing_data.low_price = data['Low']
                    existing_data.close_price = data['Close']
                    existing_data.volume = data['Volume']
                else:
                    daily_data = SP500DailyData(
                        stock_id=stock.id,
                        date=date.date(),
                        open_price=data['Open'],
                        high_price=data['High'],
                        low_price=data['Low'],
                        close_price=data['Close'],
                        volume=data['Volume']
                    )
                    db.session.add(daily_data)
            
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                continue
            
            StockData.update_monthly_stats(stock)
            
            yield stock.symbol

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
    def get_stock_info(symbol):
        ticker = yf.Ticker(symbol)
        info = ticker.info
        latest_price = StockData.get_latest_price(symbol)
        return {
            'current_pe': info.get('trailingPE'),
            'one_year_target': info.get('targetMeanPrice'),
            'earnings_date': info.get('earningsDate', [None])[0],  # Get the next earnings date
            'fifty_two_week_low': info.get('fiftyTwoWeekLow'),
            'fifty_two_week_high': info.get('fiftyTwoWeekHigh'),
            'latest_price': latest_price
        }

    @staticmethod
    def update_sp500_data(start_date):
        sp500 = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]
        
        for _, row in sp500.iterrows():
            symbol = row['Symbol']
            name = row['Security']
            sector = row['GICS Sector']
            
            stock = SP500Stock.query.filter_by(symbol=symbol).first()
            if not stock:
                print(f"Adding stock {symbol} to the database.")    
                stock = SP500Stock(symbol=symbol, name=name, sector=sector)
                db.session.add(stock)
                try:
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    print(f"Error adding stock {symbol}. It may already exist.")
                    continue
            
            # Get updated stock info
            stock_info = StockData.get_stock_info(symbol)
            
            # Update stock information
            stock.current_pe = stock_info['current_pe']
            stock.one_year_target = stock_info['one_year_target']
            stock.earnings_date = stock_info['earnings_date']
            stock.fifty_two_week_low = stock_info['fifty_two_week_low']
            stock.fifty_two_week_high = stock_info['fifty_two_week_high']
            stock.last_updated = datetime.utcnow()
            
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_date)
            
            for date, data in hist.iterrows():
                existing_data = SP500DailyData.query.filter_by(stock_id=stock.id, date=date.date()).first()
                if existing_data:
                    # Update existing data
                    existing_data.open_price = data['Open']
                    existing_data.high_price = data['High']
                    existing_data.low_price = data['Low']
                    existing_data.close_price = data['Close']
                    existing_data.volume = data['Volume']
                else:
                    # Add new data
                    daily_data = SP500DailyData(
                        stock_id=stock.id,
                        date=date.date(),
                        open_price=data['Open'],
                        high_price=data['High'],
                        low_price=data['Low'],
                        close_price=data['Close'],
                        volume=data['Volume']
                    )
                    db.session.add(daily_data)
            
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                print(f"Error updating daily data for {symbol}.")
                continue
            
            StockData.update_monthly_stats(stock)
        
        db.session.commit()

    @staticmethod
    def get_sp500_data():
        stocks = SP500Stock.query.all()
        print(f"Number of stocks returned form sp500stock table: {len(stocks)}")
        table_data = []
        
        for stock in stocks:
            latest_data = stock.daily_data.order_by(SP500DailyData.date.desc()).first()
            previous_data = stock.daily_data.order_by(SP500DailyData.date.desc()).offset(1).first()
            monthly_stats = stock.monthly_stats.order_by(SP500MonthlyStats.month.desc()).first()
            
            if latest_data and previous_data and monthly_stats:
                gain_loss = latest_data.close_price - previous_data.close_price
                gain_loss_percentage = (gain_loss / previous_data.close_price) * 100
                
                table_data.append({
                    'symbol': stock.symbol,
                    'current_price': round(latest_data.close_price, 2),
                    'previous_price': round(previous_data.close_price, 2),
                    'gain_loss': round(gain_loss, 2),
                    'gain_loss_percentage': round(gain_loss_percentage, 2),
                    'monthly_high': round(monthly_stats.high_price, 2),
                    'monthly_low': round(monthly_stats.low_price, 2),
                    'up_days': monthly_stats.up_days,
                    'down_days': monthly_stats.down_days,
                    'current_pe': stock.current_pe,
                    'one_year_target': stock.one_year_target,
                    'earnings_date': stock.earnings_date,
                    'fifty_two_week_low': stock.fifty_two_week_low,
                    'fifty_two_week_high': stock.fifty_two_week_high
                })
        
        return table_data