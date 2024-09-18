# wsgi.py
from project import create_app

app, _ = create_app()  # Unpack and use only the Flask app