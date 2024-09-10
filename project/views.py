from flask import Blueprint, render_template, redirect, request
from flask import jsonify
from .tasks import update_sp500_data
from .extensions import cache
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#from .forms import MyForm
#from .tasks import add_user

main = Blueprint('main', __name__)

'''
@main.route("/cancel/<task_id>")
def cancel(task_id):
    task = add_user.AsyncResult(task_id)
    task.abort()
    return "CANCELED!"
'''

@main.route('/update', methods=['POST'])
@cache.cached(timeout=3600)  # Cache for 1 hour
def update_data():
    logger.info("Update Button pressed - Updating S&P 500 data via submission of Celery Task")
    task = update_sp500_data.delay()
    logger.info(f"Returned from celery submission of Task ID: {task.id}")
    return jsonify({'task_id': str(task.id)}), 202

@main.route('/task/<task_id>', methods=['GET'])
def task_status(task_id):
    logger.info(f"Checking status for task ID: {task_id}")
    task = update_sp500_data.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'status': 'Pending...'
        }
    elif task.state != 'FAILURE':
        response = {
            'state': task.state,
            'status': task.info if isinstance(task.info, str) else task.info.get('status', 'Processing...')
        }
    else:
        response = {
            'state': task.state,
            'status': str(task.info) if task.info else 'An error occurred'
        }
    logger.info(f"Task status for task ID: {task_id}: {response}")
    return jsonify(response)