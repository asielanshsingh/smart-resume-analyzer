import logging
from flask import Flask, jsonify
from app.config import Config, DevelopmentConfig
from app.models import db

def create_app(config_class=DevelopmentConfig):
    """Application factory for Flask app."""
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(config_class)

    # Configure Logging
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )
    app.logger.info("Initializing Smart Resume Analyzer application...")

    # Ensure instance folder and upload folder exist
    import os
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


    # Initialize Extensions
    db.init_app(app)

    with app.app_context():
        # Ensure database tables exist
        db.create_all()

    # Register Blueprints
    from app.routes import main_bp, api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    # Top level route for /health as well
    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "ok",
            "service": "smart-resume-analyzer",
            "version": "1.0.0"
        }), 200

    # Register Global Error Handlers
    register_error_handlers(app)

    return app


def register_error_handlers(app: Flask):
    """Register custom JSON error handlers for common HTTP status codes and custom exceptions."""
    from app.services.parser import ResumeParsingError

    @app.errorhandler(ResumeParsingError)
    def handle_resume_parsing_error(error):
        return jsonify({
            "error": {
                "code": error.code,
                "message": error.message
            }
        }), error.status_code


    @app.errorhandler(400)
    def bad_request_error(error):
        message = getattr(error, "description", "Bad Request")
        return jsonify({
            "error": {
                "code": "BAD_REQUEST",
                "message": message
            }
        }), 400

    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({
            "error": {
                "code": "NOT_FOUND",
                "message": "The requested resource or endpoint was not found."
            }
        }), 404

    @app.errorhandler(413)
    def payload_too_large_error(error):
        return jsonify({
            "error": {
                "code": "PAYLOAD_TOO_LARGE",
                "message": "File size exceeds the maximum allowed limit of 16MB."
            }
        }), 413

    @app.errorhandler(415)
    def unsupported_media_type_error(error):
        return jsonify({
            "error": {
                "code": "UNSUPPORTED_MEDIA_TYPE",
                "message": "Unsupported file format. Please upload a valid PDF or DOCX file."
            }
        }), 415

    @app.errorhandler(500)
    def internal_server_error(error):
        app.logger.error(f"Server Error: {error}", exc_info=True)
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred. Please try again later."
            }
        }), 500
