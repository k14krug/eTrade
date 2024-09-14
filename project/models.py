from .extensions import db 
from flask_login import UserMixin
from datetime import datetime

'''class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
'''

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
    company_name = db.Column(db.String(100), nullable=False)
    sector = db.Column(db.String(50))
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

class SP500HistData(db.Model):
    __tablename__ = 'sp500_stock_data'
    id = db.Column(db.Integer, primary_key=True)
    stock_id = db.Column(db.Integer, db.ForeignKey('sp500stock.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    open_price = db.Column(db.Float)
    high_price = db.Column(db.Float)
    low_price = db.Column(db.Float)
    close_price = db.Column(db.Float)
    volume = db.Column(db.BigInteger)
    stock = db.relationship('SP500Stock', backref=db.backref('historical_data', lazy='dynamic'))

class SP500StockInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stock_id = db.Column(db.Integer, db.ForeignKey('sp500stock.id'), nullable=False)
    latest_price = db.Column(db.Float)
    previous_day_price = db.Column(db.Float)
    pe_ratio = db.Column(db.Float)
    one_year_target = db.Column(db.Float)
    fifty_two_week_low = db.Column(db.Float)
    fifty_two_week_high = db.Column(db.Float)
    month_high = db.Column(db.Float)
    month_low = db.Column(db.Float)
    times_above_one_percent = db.Column(db.Integer)
    times_below_one_percent = db.Column(db.Integer)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    stock = db.relationship('SP500Stock', backref=db.backref('info', uselist=False))