from flask import render_template, jsonify, request, session
from . import bp
from project.extensions import cache
from project.models import SP500Stock, SP500HistData , SP500StockPacificTime
from project.stock_data import StockData
from .tasks import update_sp500_data
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload
from sqlalchemy import and_, func


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@bp.route('/overview')
#@cache.cached(timeout=300)  # Cache for 5 minutes
@login_required
def sp500_overview():
    # Print the request arguments to debug incoming parameters
    print(f"Request Args: {request.args}")

    # Get the selected filters from the request URL parameters or session
    stock_filters = request.args.get('stock_filters', '')
    print(f"Stock Filters from Request: {stock_filters}")

    # If `stock_filters` is empty, use the session value instead of resetting
    if not stock_filters and 'stock_filters' in session:
        print("No stock_filters in request. Using session value.")
        selected_filters = session.get('stock_filters', [])
    elif stock_filters:
        # If `stock_filters` is present in the URL, update the session
        selected_filters = stock_filters.split(',')
        session['stock_filters'] = selected_filters
    else:
        # No stock_filters in request or session, reset everything
        selected_filters = []
        session.pop('stock_filters', None)

    # Debug output to verify selected filters and session state
    print(f"Selected Filters: {selected_filters}")
    print(f"Session Filters After Decision: {session.get('stock_filters')}")

    # Define filter conditions based on the view columns
    filter_conditions = {
        'filter1': SP500StockPacificTime.times_above_one_percent - SP500StockPacificTime.times_below_one_percent >= 3,
        'filter2': SP500StockPacificTime.pe_ratio < 30,
        'filter3': (SP500StockPacificTime.latest_price - SP500StockPacificTime.previous_day_price) / SP500StockPacificTime.previous_day_price * 100 >= 1,
        'filter4': (SP500StockPacificTime.latest_price - SP500StockPacificTime.previous_day_price) / SP500StockPacificTime.previous_day_price * 100 <= -1,
        'filter5': SP500StockPacificTime.latest_price < (0.9 * SP500StockPacificTime.fifty_two_week_high),
        'above_20_day_sma': SP500StockPacificTime.latest_price > SP500StockPacificTime.sma_20,
        'below_20_day_sma': SP500StockPacificTime.latest_price < SP500StockPacificTime.sma_20,
        'above_50_day_sma': SP500StockPacificTime.latest_price > SP500StockPacificTime.sma_50,
        'below_50_day_sma': SP500StockPacificTime.latest_price < SP500StockPacificTime.sma_50
    }

    # Collect conditions based on selected filters
    conditions = [filter_conditions[f] for f in selected_filters if f in filter_conditions]

    # Build the query on the view
    query = SP500StockPacificTime.query

    # Apply combined filters if any are selected
    if conditions:
        query = query.filter(and_(*conditions))

    #print(f"Final Query Conditions: {conditions}")
    #print(f"Query: {query}")

    # Get the total count of rows
    total_rows = query.count()

    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 50  # You can adjust this number or make it configurable
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Get the stocks for the current page
    stocks = pagination.items

    # Render the template with the stocks list, selected filters, pagination, and total row count
    return render_template('sp500/sp500_overview.html',
                           stocks=stocks,
                           selected_filters=selected_filters,
                           total_rows=total_rows,
                           pagination=pagination)



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

    # Fetch latest news using yfinance
    try:
        stock_news = StockData.get_stock_news(stock.symbol)
    except Exception as e:
        stock_news = []
    

    # Check if the request is for JSON data (for Plotly charts)
    if request.args.get('format') == 'json':
        # Prepare data for JSON response
        dates = [data.date.strftime('%Y-%m-%d') for data in stock_data]
        prices = [data.close_price for data in stock_data]
        volumes = [data.volume for data in stock_data]

        return jsonify({
            'dates': dates,
            'prices': prices,
            'volumes': volumes,
            'news': stock_news
        })

    # Render the HTML template with the filtered data
    return render_template('sp500/stock_detail.html', stock=stock, stock_news=stock_news, timeframe=timeframe)

@bp.route('/update', methods=['POST'])
@cache.cached(timeout=300)  # Cache for 5 minutes
def update_data():
    logger.info("Update Button pressed - Updating S&P 500 data via submission of Celery Task")
    task = update_sp500_data.delay()
    logger.info(f"Returned from celery submission of Task ID: {task.id}")
    return jsonify({'task_id': str(task.id)}), 202


