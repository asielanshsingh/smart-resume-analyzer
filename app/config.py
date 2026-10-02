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
    
    # Upload limits (Default 5MB, configurable)
    MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", 5))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    MIN_WORD_COUNT = int(os.environ.get("MIN_WORD_COUNT", 30))
    
    # Upload folder
    UPLOAD_FOLDER = BASE_DIR / "uploads"
    
    # Config File Paths
    ROLES_FILE = BASE_DIR / "data" / "roles.json"
    SCORING_CONFIG_FILE = BASE_DIR / "data" / "scoring_config.json"
    SUGGESTIONS_FILE = BASE_DIR / "data" / "suggestions.json"
    SECTIONS_CONFIG_FILE = BASE_DIR / "data" / "sections.json"
    
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
