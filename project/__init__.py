# File: ./project/__init__.py

from flask import Flask
from .extensions import db, cache, migrate
from .utils import make_celery
from .config import config
import os
from flask_login import LoginManager
from flask_cors import CORS

login_manager = LoginManager()

def is_auto_reload():
    """Check if the app is being reloaded due to code changes in development."""
    return os.getenv('WERKZEUG_RUN_MAIN') == 'True'

def submit_initial_tasks(celery):
    """Submit SP500 update task only if it's the initial startup (not a reload)."""
    if not is_auto_reload():
        print("Submitting SP500 data update task...")
        celery.send_task('update_sp500_data')
    else:
        print("Skipping task submission due to auto-reload.")

def create_app(config_name=None):
    app = Flask(__name__)
    
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')
    
    app.config.from_object(config[config_name])

    login_manager.init_app(app)
    login_manager.login_view = 'main.login'

    # Register blueprints
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .transactions import bp as transactions_bp
    app.register_blueprint(transactions_bp, url_prefix='/transactions')

    from .sp500 import bp as sp500_bp
    app.register_blueprint(sp500_bp, url_prefix='/sp500')

    db.init_app(app)
    cache.init_app(app) 
    migrate.init_app(app, db)
   
    # Import the tasks so Celery registers them
    from project.sp500 import tasks

    # Initialize Celery
    celery = make_celery(app)
    celery.set_default()

    # Submit the Celery task if this is the first startup (not during an auto-reload)
    submit_initial_tasks(celery)

    return app, celery  

@login_manager.user_loader
def load_user(user_id):
    from .models import User  # Import here to avoid circular imports
    return User.query.get(int(user_id))
