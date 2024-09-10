import os
from project import create_app
from project.extensions import db

config_name = os.getenv('FLASK_CONFIG') or 'default'
app, _ = create_app(config_name)

with app.app_context():
    db.create_all()