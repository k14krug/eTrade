from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    starting_balance = db.Column(db.Float, default=0.0)
    transactions = db.relationship('Transactions', backref='user', lazy='dynamic')

class Transactions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    transaction_type = db.Column(db.String(20), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    commission = db.Column(db.Float, nullable=False)
    cash_balance = db.Column(db.Float, nullable=False)
    stock_value = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Position(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    average_price = db.Column(db.Float, nullable=False)
    user = db.relationship('User', backref=db.backref('positions', lazy='dynamic'))

class SP500Stock(db.Model):
    __tablename__ = 'sp500stock'
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sector = db.Column(db.String(50))
    current_pe = db.Column(db.Float)
    one_year_target = db.Column(db.Float)
    earnings_date = db.Column(db.String(50))  # Store as string for flexibility
    fifty_two_week_low = db.Column(db.Float)
    fifty_two_week_high = db.Column(db.Float)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

class SP500DailyData(db.Model):
    __tablename__ = 'sp500dailydata'
    id = db.Column(db.Integer, primary_key=True)
    stock_id = db.Column(db.Integer, db.ForeignKey('sp500stock.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    open_price = db.Column(db.Float, nullable=False)
    high_price = db.Column(db.Float, nullable=False)
    low_price = db.Column(db.Float, nullable=False)
    close_price = db.Column(db.Float, nullable=False)
    volume = db.Column(db.BigInteger, nullable=False)
    
    stock = db.relationship('SP500Stock', backref=db.backref('daily_data', lazy='dynamic'))

class SP500MonthlyStats(db.Model):
    __tablename__ = 'sp500monthlystats'
    id = db.Column(db.Integer, primary_key=True)
    stock_id = db.Column(db.Integer, db.ForeignKey('sp500stock.id'), nullable=False)
    month = db.Column(db.Date, nullable=False)
    high_price = db.Column(db.Float, nullable=False)
    low_price = db.Column(db.Float, nullable=False)
    up_days = db.Column(db.Integer, default=0)
    down_days = db.Column(db.Integer, default=0)
    
    stock = db.relationship('SP500Stock', backref=db.backref('monthly_stats', lazy='dynamic'))