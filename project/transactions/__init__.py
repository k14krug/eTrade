from flask import Blueprint

bp = Blueprint('transactions', __name__)

from . import routes