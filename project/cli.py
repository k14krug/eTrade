# cli.py

import click
from flask.cli import with_appcontext
from datetime import datetime
from .sp500_hist_initializer import initialize_sp500_data

@click.command('init-sp500')
@click.option('--start-date', default=None, help='Start date for historical data (YYYY-MM-DD)')
@with_appcontext
def init_sp500_command(start_date):
    """Initialize S&P 500 stock data."""
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
    initialize_sp500_data(start_date)
    click.echo('S&P 500 data initialized.')