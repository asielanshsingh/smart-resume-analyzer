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

@main_bp.route("/result/<share_token>")
def result(share_token):
    """Render interactive analysis dashboard page for a share token or analysis ID."""
    return render_template("dashboard.html")

