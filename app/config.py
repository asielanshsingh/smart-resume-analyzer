import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    
    # SQLite Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'app.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload limits (16 MB default)
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))
    
    # Config File Paths
    ROLES_FILE = BASE_DIR / "data" / "roles.json"
    SCORING_CONFIG_FILE = BASE_DIR / "data" / "scoring_config.json"
    SUGGESTIONS_FILE = BASE_DIR / "data" / "suggestions.json"
    
    # Allowed File Extensions
    ALLOWED_EXTENSIONS = {"pdf", "docx"}


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
