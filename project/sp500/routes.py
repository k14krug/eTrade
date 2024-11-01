from flask import render_template, jsonify, request, session, redirect, url_for
from . import bp
from project.extensions import cache
from project.models import SP500Stock, SP500HistData , SP500StockPacificTime
from project.stock_data import StockData
from .tasks import update_sp500_data
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload
from sqlalchemy import and_, func, and_, select
import json


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Local storage for watchlist and notes
WATCHLIST_FILE = 'watchlist.json'

@bp.route('/overview')
#@cache.cached(timeout=300)  # Cache for 5 minutes
@login_required
def sp500_overview():
    
    # Load the watchlist to check for existing notes
    watchlist = load_watchlist()
    # Create a dictionary of watch notes for quick lookup
    watchlist_notes = {}
    for symbol, notes in watchlist.get('notes', {}).items():
        if isinstance(notes, list) and notes:
            # If there are multiple notes, store the most recent one
            watchlist_notes[symbol] = notes[-1]['text']
        else:
            watchlist_notes[symbol] = ""

    # Get query parameters for search, pagination, and filters
    search_query = request.args.get('search_query', '', type=str)
    #print(f"Search Query: {search_query}")
    stock_filters = request.args.get('stock_filters', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)  # Default rows per page
    sort_column = request.args.get('sort', 'symbol')  # Default sort by symbol
    sort_direction = request.args.get('direction', 'asc')  # Default ascending
    
    print(f"[DEBUG] Search Query: {search_query}")
    print(f"[DEBUG] Selected Filters: {stock_filters}")
    print(f"[DEBUG] Page: {page}, Per Page: {per_page}")

    # If `stock_filters` is empty, use the session value instead of resetting
    if not stock_filters and 'stock_filters' in session:
        selected_filters = session.get('stock_filters', [])
    elif stock_filters:
        # If `stock_filters` is present in the URL, update the session
        selected_filters = stock_filters.split(',')
        session['stock_filters'] = selected_filters
    else:
        # No stock_filters in request or session, reset everything
        selected_filters = []
        session.pop('stock_filters', None)

    
    # Calculate dates for the 30-day and 90-day windows
    today = datetime.utcnow().date()
    date_30_days_ago = today - timedelta(days=30)
    date_90_days_ago = today - timedelta(days=90)

    # Subqueries for 30-day and 90-day percent changes
    percent_change_30_days = (
        (func.max(SP500HistData.close_price) - func.min(SP500HistData.close_price)) /
        func.min(SP500HistData.close_price) * 100
    ).label("percent_change_30_days")

    percent_change_90_days = (
        (func.max(SP500HistData.close_price) - func.min(SP500HistData.close_price)) /
        func.min(SP500HistData.close_price) * 100
    ).label("percent_change_90_days")

    subquery_30_days = (
        select(SP500HistData.stock_id, percent_change_30_days)
        .where(SP500HistData.date >= date_30_days_ago)
        .group_by(SP500HistData.stock_id)
        .subquery()
    )

    subquery_90_days = (
        select(SP500HistData.stock_id, percent_change_90_days)
        .where(SP500HistData.date >= date_90_days_ago)
        .group_by(SP500HistData.stock_id)
        .subquery()
    )

    # Correctly join subqueries with SP500StockPacificTime
    query = (
        SP500StockPacificTime.query
        .outerjoin(subquery_30_days, subquery_30_days.c.stock_id == SP500StockPacificTime.id)
        .outerjoin(subquery_90_days, subquery_90_days.c.stock_id == SP500StockPacificTime.id)
    )

    # [DEBUG] Check initial row count after joining
    query_count = query.count()
    print(f"[DEBUG] Initial Row Count (Before Filters): {query_count}")
    print(f"[DEBUG] Initial Query: {query}")


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
        'below_50_day_sma': SP500StockPacificTime.latest_price < SP500StockPacificTime.sma_50,
        # find stocks that are not more than 2% gain or loss in the last 30 days and not more than 10% in the last 90 days
        'within_2_percent_30_days': subquery_30_days.c.percent_change_30_days <= 2,
        'within_10_percent_gain_90_days': subquery_90_days.c.percent_change_90_days <= 10,
        'down_1_percent': (
            (SP500StockPacificTime.latest_price - SP500StockPacificTime.previous_day_price) /
            SP500StockPacificTime.previous_day_price * 100
        ) <= -1
    }

    # Collect conditions based on selected filters
    conditions = [filter_conditions[f] for f in selected_filters if f in filter_conditions]
    # Apply combined filters if any are selected
    if conditions:
        query = query.filter(and_(*conditions))
    
    query_count = query.count()
    print(f"[DEBUG] 2nd Row Count (After conditions): {query_count}")
    
    # Apply search query filter
    if search_query:
        query = query.filter(
            SP500StockPacificTime.symbol.ilike(f'%{search_query}%') |
            SP500StockPacificTime.company_name.ilike(f'%{search_query}%') |
            SP500StockPacificTime.sector.ilike(f'%{search_query}%')
        )

    query_count = query.count()
    print(f"[DEBUG] 4th Row Count (After Conditions): {query_count}")
    print(f"[DEBUG] 4th Query: {query}")

    # Define sorting logic
    column_mapping = {
        'symbol': SP500StockPacificTime.symbol,
        'company_name': SP500StockPacificTime.company_name,
        'sector': SP500StockPacificTime.sector,
        'latest_price': SP500StockPacificTime.latest_price,
        'previous_day_price': SP500StockPacificTime.previous_day_price,
        'gain_loss_percent': (SP500StockPacificTime.latest_price - SP500StockPacificTime.previous_day_price) / SP500StockPacificTime.previous_day_price * 100,
        'month_high': SP500StockPacificTime.month_high,
        'month_low': SP500StockPacificTime.month_low,
        'pe_ratio': SP500StockPacificTime.pe_ratio,
        'one_year_target': SP500StockPacificTime.one_year_target,
        'fifty_two_week_range': SP500StockPacificTime.fifty_two_week_high - SP500StockPacificTime.fifty_two_week_low,
        'times_above_one_percent': SP500StockPacificTime.times_above_one_percent,
        'times_below_one_percent': SP500StockPacificTime.times_below_one_percent,
        'last_updated_pacific': SP500StockPacificTime.last_updated_pacific,
    }

    # Apply sorting
    page_sort_column = sort_column
    sort_column = column_mapping.get(sort_column, SP500StockPacificTime.symbol)
    if sort_direction == 'desc':
        sort_column = sort_column.desc()
    print(f"sort_column: {sort_column}")
    query = query.order_by(sort_column)
    query_count = query.count()    

    # Get the total count of rows
    total_rows = query.count()
    print(f"[DEBUG] Final Row Count: {query_count}")
    

    # Pagination
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Get the stocks for the current page
    stocks = pagination.items   

    # Render the template with the stocks list, selected filters, pagination, and total row count
    return render_template('sp500/sp500_overview.html',
                            stocks=stocks,
                            selected_filters=selected_filters,
                            total_rows=total_rows,
                            watchlist_notes=watchlist_notes,
                            pagination=pagination,
                            search_query=search_query,
                            per_page=per_page,
                            sort_column=page_sort_column,
                            #sort_column=sort_column.key if hasattr(sort_column, 'key') else sort_column,
                            sort_direction=sort_direction)


@bp.route('/stock/<symbol>', methods=['GET'])
@login_required
def stock_detail(symbol):

    # Get basic stock information from the SP500Stock table
    stock = SP500Stock.query.filter_by(symbol=symbol).first_or_404()

    # Get the selected timeframe from the request parameters
    timeframe = request.args.get('timeframe', '1y')  # Default to 1 year if not specified
    
    if timeframe == 'intraday':
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
@login_required
@cache.cached(timeout=300)  # Cache for 5 minutes
def update_data():
    logger.info("Update Button pressed - Updating S&P 500 data via submission of Celery Task")
    task = update_sp500_data.delay()
    logger.info(f"Returned from celery submission of Task ID: {task.id}")
    return jsonify({'task_id': str(task.id)}), 202

# Utility function to load watchlist
def load_watchlist():
    try:
        with open(WATCHLIST_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {"stocks": [], "notes": {}}

# Utility function to save watchlist
def save_watchlist(watchlist):
    with open(WATCHLIST_FILE, 'w') as file:
        json.dump(watchlist, file)

@bp.route('/watchlist', methods=['GET', 'POST'])
@login_required
def watchlist():
    watchlist = load_watchlist()

    if request.method == 'POST':
        # Handle adding or removing stocks
        action = request.form.get('action')
        symbol = request.form.get('symbol').upper()

        if action == 'add' and symbol and symbol not in watchlist['stocks']:
            watchlist['stocks'].append(symbol)
        elif action == 'remove' and symbol in watchlist['stocks']:
            watchlist['stocks'].remove(symbol)
            watchlist['notes'].pop(symbol, None)  # Remove associated notes

        save_watchlist(watchlist)
        return redirect(url_for('sp500.watchlist'))

    # Extract the most recent note for each stock
    recent_notes = {}
    for stock in watchlist['stocks']:
        if stock in watchlist['notes'] and isinstance(watchlist['notes'][stock], list):
            # Get the most recent note based on the last entry in the list
            recent_notes[stock] = watchlist['notes'][stock][-1]['text']
        else:
            recent_notes[stock] = ""  # No notes available

    # Query the SP500Stock table to get company details
    stock_details = {}
    for stock in watchlist['stocks']:
        # Query the SP500Stock table for each stock symbol
        stock_info = SP500Stock.query.filter_by(symbol=stock).first()
        if stock_info:
            stock_details[stock] = {
                "company_name": stock_info.company_name,
                "sector": stock_info.sector
            }
        else:
            # Handle missing stock details gracefully
            stock_details[stock] = {
                "company_name": "Unknown",
                "sector": "Unknown"
            }

    return render_template('sp500/watchlist.html',
                           watchlist=watchlist['stocks'],
                           recent_notes=recent_notes,
                           stock_details=stock_details)



@bp.route('/watchlist/<symbol>', methods=['GET', 'POST'])
@login_required
def watchlist_detail(symbol):
    symbol = symbol.upper()

    # Load the watchlist from the JSON file
    watchlist = load_watchlist()

    # Check if the stock is already in the watchlist; if not, add it
    if symbol not in watchlist['stocks']:
        watchlist['stocks'].append(symbol)
        watchlist['notes'][symbol] = []  # Initialize an empty list for storing multiple notes
        save_watchlist(watchlist)

    if request.method == 'POST':
        # Get the new note from the form
        note_text = request.form.get('note')
        if note_text:
            # Create a new note entry with a timestamp
            new_note = {
                "text": note_text,
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }   

            # Check if the notes for the symbol are stored as a list
            if not isinstance(watchlist['notes'].get(symbol), list):
                # If it's not a list (legacy format), convert it to a list of entries
                watchlist['notes'][symbol] = [{"text": watchlist['notes'][symbol], "timestamp": "Legacy Note"}]

            # Append the new note to the existing notes list for the stock
            watchlist['notes'][symbol].append(new_note)
            save_watchlist(watchlist)
        return redirect(url_for('sp500.watchlist_detail', symbol=symbol))

    # Retrieve stock details from the SP500Stock table
    stock_info = SP500Stock.query.filter_by(symbol=symbol).first()
    stock_details = {
        "company_name": stock_info.company_name if stock_info else "Unknown",
        "sector": stock_info.sector if stock_info else "Unknown"
    }

    # Render the detailed page with all existing notes
    existing_notes = watchlist['notes'].get(symbol, [])
    return render_template('sp500/watchlist_detail.html',
                           symbol=symbol,
                           notes=existing_notes,
                           stock_details=stock_details)




