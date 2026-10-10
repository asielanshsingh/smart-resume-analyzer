from flask import Blueprint

main_bp = Blueprint("main", __name__)
api_bp = Blueprint("api", __name__)

from app.routes import api, main  # noqa: F401
