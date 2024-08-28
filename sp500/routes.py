# sp500/routes.py
from flask import Blueprint, render_template, request
from stock_data import StockData

sp500_bp = Blueprint('sp500', __name__)

@sp500_bp.route('/', methods=['GET'])
def sp500():
    table_data = StockData.get_sp500_data()

    sort_by = request.args.get('sort_by', 'symbol')
    sort_order = request.args.get('sort_order', 'asc')

    table_data = sorted(table_data, key=lambda x: x[sort_by], reverse=(sort_order == 'desc'))

    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 100))
    total_pages = (len(table_data) + per_page - 1) // per_page

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_data = table_data[start_idx:end_idx]

    return render_template('sp500.html', 
                           data=paginated_data, 
                           page=page, 
                           total_pages=total_pages, 
                           sort_by=sort_by, 
                           sort_order=sort_order)