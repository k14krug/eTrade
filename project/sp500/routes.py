from flask import render_template, jsonify, request
from . import bp
from project.extensions import cache
from project.models import SP500Stock, SP500HistData , SP500StockInfo
from project.stock_data import StockData
from .tasks import update_sp500_data
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload
from sqlalchemy import and_

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@bp.route('/overview')
#@cache.cached(timeout=300)  # Cache for 5 minutes
@login_required
def sp500_overview():
    # Get the selected filters from the request
    selected_filters = request.args.get('stock_filters', '').split(',')

    # Define filter conditions with correct attribute access through the 'info' relationship
    filter_conditions = {
        'filter1': SP500Stock.info.has(SP500StockInfo.times_above_one_percent - SP500StockInfo.times_below_one_percent >= 3),
        'filter2': SP500Stock.info.has(SP500StockInfo.pe_ratio < 30),
        # Add more filters as necessary
    }

    # Collect conditions based on selected filters
    conditions = [filter_conditions[f] for f in selected_filters if f in filter_conditions]

    # Build the query, ensuring related info is loaded
    query = SP500Stock.query.options(joinedload(SP500Stock.info))
    
    # Apply combined filters if any are selected
    if conditions:
        query = query.filter(and_(*conditions))

    # Execute the query
    stocks = query.all()
    print(f"number of stocks: {len(stocks)}")

    # Render the template with the stocks list
    return render_template('sp500/sp500_overview.html', stocks=stocks)

@bp.route('/stock/<symbol>', methods=['GET'])
def stock_detail(symbol):
    stock = SP500Stock.query.filter_by(symbol=symbol).first_or_404()

    # Get the selected timeframe from the request parameters
    timeframe = request.args.get('timeframe', '1y')  # Default to 1 year if not specified
    

    if timeframe == 'intraday':
        #print("Intraday selected")
        # Fetch intraday data for the stock using yfinance
        intraday_data = StockData.get_intraday_data(stock.symbol)
        # Check if the request is for JSON data (for Plotly charts)
        if request.args.get('format') == 'json':
            return jsonify(intraday_data)
        # If not JSON, render template with intraday data
        return render_template('sp500/stock_detail.html', stock=stock, stock_data=intraday_data, timeframe=timeframe)
    elif timeframe == '5d':
        five_business_days = StockData.get_intraday_data(stock.symbol,5)
        # Check if the request is for JSON data (for Plotly charts)
        if request.args.get('format') == 'json':
            return jsonify(five_business_days)
        # If not JSON, render template with intraday data
        return render_template('sp500/stock_detail.html', stock=stock, stock_data=five_business_days, timeframe=timeframe)
  

    # Determine the start date based on the selected timeframe
    if timeframe == 'max':
        start_date = None  # No filtering, return all data
    elif timeframe == '1y':
        start_date = datetime.now() - timedelta(days=365)
    elif timeframe == 'ytd':
        start_date = datetime(datetime.now().year, 1, 1)
    elif timeframe == '3m':
        start_date = datetime.now() - timedelta(days=90)
    elif timeframe == '1m':
        start_date = datetime.now() - timedelta(days=30)
    #elif timeframe == '5d':
    #    start_date = datetime.now() - timedelta(days=5)
    else:
        start_date = datetime.now() - timedelta(days=365)  # Default to 1 year if invalid

    # Fetch historical data based on the calculated start date
    if start_date is not None:
        start_date = start_date.date() # Convert to date type
        # Apply date filter when start_date is not None
        stock_data = SP500HistData.query.filter(
            SP500HistData.stock_id == stock.id,
            SP500HistData.date >= start_date
        ).order_by(SP500HistData.date).all()
    else:
        # Return all data when start_date is None (Max option)
        stock_data = SP500HistData.query.filter_by(
            stock_id=stock.id
        ).order_by(SP500HistData.date).all()        
    
    # Check if the request is for JSON data (for Plotly charts)
    if request.args.get('format') == 'json':
        # Prepare data for JSON response
        dates = [data.date.strftime('%Y-%m-%d') for data in stock_data]
        prices = [data.close_price for data in stock_data]
        volumes = [data.volume for data in stock_data]

        return jsonify({
            'dates': dates,
            'prices': prices,
            'volumes': volumes
        })

    # Render the HTML template with the filtered data
    return render_template('sp500/stock_detail.html', stock=stock, stock_data=stock_data, timeframe=timeframe)

@bp.route('/update', methods=['POST'])
@cache.cached(timeout=300)  # Cache for 5 minutes
def update_data():
    logger.info("Update Button pressed - Updating S&P 500 data via submission of Celery Task")
    task = update_sp500_data.delay()
    logger.info(f"Returned from celery submission of Task ID: {task.id}")
    return jsonify({'task_id': str(task.id)}), 202


