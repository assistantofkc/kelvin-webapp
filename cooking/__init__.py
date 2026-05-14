from flask import Blueprint

cooking_bp = Blueprint('cooking', __name__, template_folder='../templates/cooking', static_folder='../static/cooking')

from . import routes
