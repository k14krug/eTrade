from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, DateTime
from sqlalchemy.sql import text

# Step 1: Create an engine and connect to the database
engine = create_engine('sqlite:////mnt/wsl_projects/eTrade/instance/eTrade.sqlite')

# Step 2: Reflect the existing database schema
metadata = MetaData()
metadata.reflect(bind=engine)

# Step 3: Define the existing table
sp500stock = Table('sp500stock', metadata, autoload_with=engine)

# Step 4: Define the new columns
new_columns = [
    Column('one_year_target', Float),
    Column('earnings_date', String(50)),
    Column('fifty_two_week_low', Float),
    Column('fifty_two_week_high', Float)
]

# Step 5: Use the alter method to add the new columns
with engine.connect() as conn:
    for column in new_columns:
        conn.execute(text(f'ALTER TABLE sp500stock ADD COLUMN {column.compile(dialect=engine.dialect)}'))

# Verify the changes
metadata.reflect(bind=engine)
print(sp500stock.columns.keys())