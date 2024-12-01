import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from project.models import SP500Stock
from project.extensions import db
from project import create_app

app = create_app()
if isinstance(app, tuple):
    app = app[0]
app.app_context().push()

sector_etfs = {
    'Communication Services': 'XLC',
    'Consumer Discretionary': 'XLY',
    'Consumer Staples': 'XLP',
    'Energy': 'XLE',
    'Financials': 'XLF',
    'Health Care': 'XLV',
    'Industrials': 'XLI',
    'Information Technology': 'XLK',
    'Materials': 'XLB',
    'Real Estate': 'XLRE',
    'Utilities': 'XLU'
}

for sector, symbol in sector_etfs.items():
    stock_record = SP500Stock.query.filter_by(symbol=symbol).first()
    if not stock_record:
        stock_record = SP500Stock(symbol=symbol, company_name=sector, sector=sector)
        db.session.add(stock_record)

db.session.commit()
print("Sector indexes inserted successfully.")