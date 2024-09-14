from flask import Flask
from .extensions import db, cache
#from .routes import main
from .utils import make_celery
from .config import config
import os
from flask_login import LoginManager
from flask_cors  import CORS

login_manager = LoginManager()

def create_app(config_name=None):
    app = Flask(__name__)
    
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')
    
    app.config.from_object(config[config_name])

    login_manager.init_app(app)
    login_manager.login_view = 'main.login'

    # Register blueprints
    from .routes import main as main_blueprint
    #app.register_blueprint(main)
    app.register_blueprint(main_blueprint)

    from .transactions import bp as transactions_bp
    app.register_blueprint(transactions_bp, url_prefix='/transactions')

    from .sp500 import bp as sp500_bp
    app.register_blueprint(sp500_bp, url_prefix='/sp500')

    db.init_app(app)
    cache.init_app(app) 

    celery = make_celery(app)
    celery.set_default()

    # Register CLI command
    from .cli import init_sp500_command
    app.cli.add_command(init_sp500_command)

    return app, celery  

@login_manager.user_loader
def load_user(user_id):
    from .models import User  # Import here to avoid circular imports
    return User.query.get(int(user_id))