from flask import render_template, jsonify
from . import bp
from project.extensions import cache
from project.models import SP500Stock, SP500HistData
from .tasks import update_sp500_data, update_sp500_hist_data
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@bp.route('/overview')
@login_required
def sp500_overview():
    stocks = SP500Stock.query.all()
    return render_template('sp500/sp500_overview.html', stocks=stocks)

@bp.route('/stock/<symbol>')
def stock_detail(symbol):
    stock = SP500Stock.query.filter_by(symbol=symbol).first_or_404()
    return render_template('sp500/stock_detail.html', stock=stock)

@bp.route('/update', methods=['POST'])
@cache.cached(timeout=300)  # Cache for 1 hour
def update_data():
    logger.info("Update Button pressed - Updating S&P 500 data via submission of Celery Task")
    task = update_sp500_data.delay()
    logger.info(f"Returned from celery submission of Task ID: {task.id}")
    return jsonify({'task_id': str(task.id)}), 202

@bp.route('/update_hist_data', methods=['POST'])
@cache.cached(timeout=300)  # Cache for 1 hour
def update_hist_data():
    logger.info("Update Button pressed - Updating S&P 500 hist data via submission of Celery Task")
    task = update_sp500_hist_data.delay()
    logger.info(f"Returned from celery submission of Task ID: {task.id}")
    return jsonify({'task_id': str(task.id)}), 202

@bp.route('/stock/<symbol>/historical')
def stock_historical_data(symbol):
    stock = SP500Stock.query.filter_by(symbol=symbol).first_or_404()
    historical_data = SP500HistData.query.filter_by(stock_id=stock.id).order_by(SP500HistData.date).all()

    dates = [data.date.strftime('%Y-%m-%d') for data in historical_data]
    prices = [data.close_price for data in historical_data]
    volumes = [data.volume for data in historical_data]

    return jsonify({
        'dates': dates,
        'prices': prices,
        'volumes': volumes
    })

'''
@sp500_bp.route('/overview')
@cache.cached(timeout=3600)  # Cache for 1 hour
def sp500_overview():
    stocks = SP500Stock.query.all()
    return render_template('sp500_overview.html', stocks=stocks)
'''