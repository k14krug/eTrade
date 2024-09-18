from flask import Blueprint, render_template, redirect, request
from flask import jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask import flash, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from .forms import LoginForm, RegistrationForm
from .sp500.tasks import update_sp500_data
from .models import User
from .extensions import cache
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#from .forms import MyForm
#from .tasks import add_user

main = Blueprint('main', __name__)

@main.route('/')
def home():
    return redirect(url_for('transactions.transactions'))

@main.route('/admin')
def admin_panel():
    return render_template('admin.html')

@main.route("/cancel/<task_id>")
def cancel(task_id):
    task = update_sp500_data.AsyncResult(task_id)
    logger.info(f"Canceling task ID: {task_id}")
    task.abort()
    return "Task canceled successfully"

@main.route('/clear_cache', methods=['POST'])
def clear_cache():
    try:
        cache.clear()
        logger.info("Cache cleared successfully")
        return jsonify({"message": "Cache cleared successfully"}), 200
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        return jsonify({"error": "Failed to clear cache"}), 500

@main.route('/update', methods=['POST'])
@cache.cached(timeout=300)  # Cache for 1 hour
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

@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.home'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html', title='Sign In', form=form)

@main.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data, 
                    starting_balance=form.starting_balance.data)
        user.password_hash = generate_password_hash(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.home'))