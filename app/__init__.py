import logging
import os
from flask import Flask, jsonify
from app.config import Config, DevelopmentConfig
from app.models import db


def create_app(config_class: type = DevelopmentConfig) -> Flask:
    """Application factory for the Smart Resume Analyzer."""
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(config_class)

    # Configure structured logging
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
    )
    app.logger.info("Initializing Smart Resume Analyzer application...")

    # Ensure required directories exist
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Initialize extensions
    db.init_app(app)

    with app.app_context():
        # Auto-create tables on every cold start (safe if tables already exist)
        db.create_all()

        # Schema migration: add share_token column to legacy databases
        _migrate_share_token(app)

    # Register blueprints
    from app.routes import main_bp, api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    # Health check (also exposed via api_bp at /api/health)
    @app.route("/health", methods=["GET"])
    def health():
        return jsonify(
            {"status": "ok", "service": "smart-resume-analyzer", "version": "1.0.0"}
        ), 200

    # Security headers on every response
    @app.after_request
    def apply_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    register_error_handlers(app)

    return app


def _migrate_share_token(app: Flask) -> None:
    """Add share_token column to analyses table if it is missing (one-time migration)."""
    try:
        from sqlalchemy import inspect, text
        import secrets

        inspector = inspect(db.engine)
        if "analyses" not in inspector.get_table_names():
            return

        columns = [c["name"] for c in inspector.get_columns("analyses")]
        if "share_token" in columns:
            return

        app.logger.info(
            "Migrating database: adding share_token column to analyses table..."
        )
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE analyses ADD COLUMN share_token VARCHAR(64)"))

        # Backfill existing rows
        from app.models import Analysis

        legacy_rows = Analysis.query.filter(
            (Analysis.share_token == None) | (Analysis.share_token == "")  # noqa: E711
        ).all()
        for row in legacy_rows:
            row.share_token = secrets.token_urlsafe(16)
        db.session.commit()
    except Exception as migration_err:
        app.logger.warning("Database schema migration warning: %s", migration_err)


def register_error_handlers(app: Flask) -> None:
    """Register JSON error handlers for common HTTP status codes."""
    from app.services.parser import ResumeParsingError

    @app.errorhandler(ResumeParsingError)
    def handle_resume_parsing_error(error):
        return jsonify(
            {"error": {"code": error.code, "message": error.message}}
        ), error.status_code

    @app.errorhandler(400)
    def bad_request_error(error):
        message = getattr(error, "description", "Bad Request")
        return jsonify({"error": {"code": "BAD_REQUEST", "message": message}}), 400

    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify(
            {
                "error": {
                    "code": "NOT_FOUND",
                    "message": "The requested resource or endpoint was not found.",
                }
            }
        ), 404

    @app.errorhandler(405)
    def method_not_allowed_error(error):
        return jsonify(
            {
                "error": {
                    "code": "METHOD_NOT_ALLOWED",
                    "message": "HTTP method not allowed for this endpoint.",
                }
            }
        ), 405

    @app.errorhandler(413)
    def payload_too_large_error(error):
        max_mb = app.config.get("MAX_UPLOAD_MB", 16)
        return jsonify(
            {
                "error": {
                    "code": "PAYLOAD_TOO_LARGE",
                    "message": f"File size exceeds the maximum allowed limit of {max_mb}MB.",
                }
            }
        ), 413

    @app.errorhandler(415)
    def unsupported_media_type_error(error):
        return jsonify(
            {
                "error": {
                    "code": "UNSUPPORTED_MEDIA_TYPE",
                    "message": "Unsupported file format. Please upload a valid PDF or DOCX file.",
                }
            }
        ), 415

    @app.errorhandler(500)
    def internal_server_error(error):
        # Log with traceback server-side; never expose it to the client
        app.logger.error("Internal server error: %s", error, exc_info=True)
        return jsonify(
            {
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An internal server error occurred. Please try again later.",
                }
            }
        ), 500
