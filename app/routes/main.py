from flask import Response, render_template

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


@main_bp.route("/robots.txt", methods=["GET"])
def robots_txt():
    """Advisory crawler policy: keep bots out of the API and per-user pages."""
    policy = "\n".join([
        "User-agent: *",
        "Disallow: /api/",
        "Disallow: /dashboard",
        "Disallow: /result/",
        "Allow: /",
        "",
    ])
    return Response(policy, mimetype="text/plain")


@main_bp.route("/.well-known/security.txt", methods=["GET"])
def security_txt():
    """RFC 9116 security contact disclosure."""
    body = "\n".join([
        "Contact: mailto:asielanshsingh@gmail.com",
        "Expires: 2027-10-14T00:00:00.000Z",
        "Preferred-Languages: en",
        "Canonical: https://smart-resume-analyzer-4lji.onrender.com/.well-known/security.txt",
        "",
    ])
    return Response(body, mimetype="text/plain")
