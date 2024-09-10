from flask import Flask
from .extensions import db, cache
from .views import main
from .utils import make_celery
#from .config import onfig

def create_app():
    app = Flask(__name__)
    
    #app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite3"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///eTrade.sqlite"
    app.config["SECRET_KEY"] = "&DwoQK)g%*Wit2YpE#-46Oz8Z7Iuvy0n"
    app.config["CELERY_CONFIG"] = {"broker_url": "redis://localhost:6379/0", "result_backend": "redis://localhost:6379/0"}
    #app.config["CELERY_CONFIG"] = {"broker_url": "redis://redis", "result_backend": "redis://redis"}

    # Cache configuration
    app.config["CACHE_TYPE"] = "redis"
    app.config["CACHE_REDIS_URL"] = "redis://localhost:6379/1"


    db.init_app(app)
    cache.init_app(app) 

    celery = make_celery(app)
    celery.set_default()
    
    app.register_blueprint(main)

    return app, celery