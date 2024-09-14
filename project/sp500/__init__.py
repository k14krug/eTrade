from flask import Blueprint

bp = Blueprint('sp500', __name__)

from . import routes