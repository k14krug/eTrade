import os

class Config:
    


    SECRET_KEY = os.environ.get('SECRET_KEY') or "&DwoQK)g%*Wit2YpE#-46Oz8Z7Iuvy0n"
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or "mysql+pymysql://etrade_user:admin14@localhost/etrade_db"
    #SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or "sqlite:///eTrade.sqlite"

    CELERY_CONFIG = {
        "broker_url": os.environ.get('CELERY_BROKER_URL') or "redis://localhost:6379/0",
        "result_backend": os.environ.get('CELERY_RESULT_BACKEND') or "redis://localhost:6379/0"
    }
    CACHE_TYPE = "redis"
    CACHE_REDIS_URL = os.environ.get('CACHE_REDIS_URL') or "redis://localhost:6379/1"
    FINNHUB_API_KEY = os.environ.get('FINNHUB_API_KEY') or "ct3la79r01qrd05j4vagct3la79r01qrd05j4vb0"

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}