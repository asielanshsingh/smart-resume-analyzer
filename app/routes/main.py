from flask import render_template
from app.routes import main_bp

@main_bp.route("/")
def index():
    """Render resume upload & role selection page."""
    return render_template("index.html")

@main_bp.route("/dashboard")
def dashboard():
    """Render interactive analysis dashboard page."""
    return render_template("dashboard.html")
