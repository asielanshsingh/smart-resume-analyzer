import os
from pathlib import Path
from typing import ClassVar

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Base application configuration."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

    # SQLite Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'app.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload limits (default 5 MB, configurable via MAX_UPLOAD_MB env var)
    MAX_UPLOAD_MB: int = int(os.environ.get("MAX_UPLOAD_MB", "5"))
    MAX_CONTENT_LENGTH: int = MAX_UPLOAD_MB * 1024 * 1024
    MIN_WORD_COUNT: int = int(os.environ.get("MIN_WORD_COUNT", "30"))

    # Upload folder
    UPLOAD_FOLDER = BASE_DIR / "uploads"

    # Config File Paths
    ROLES_FILE = BASE_DIR / "data" / "roles.json"
    SCORING_CONFIG_FILE = BASE_DIR / "data" / "scoring_config.json"
    SUGGESTIONS_FILE = BASE_DIR / "data" / "suggestions.json"
    SECTIONS_CONFIG_FILE = BASE_DIR / "data" / "sections.json"
    ATS_CONFIG_FILE = BASE_DIR / "data" / "ats_config.json"
    SKILLS_FILE = BASE_DIR / "data" / "skills.json"

    # Custom Job Description Limit
    MAX_JD_LENGTH: int = int(os.environ.get("MAX_JD_LENGTH", "10000"))

    # Allowed File Extensions (ClassVar so ruff/mypy don't treat it as a mutable default)
    ALLOWED_EXTENSIONS: ClassVar[set[str]] = {"pdf", "docx"}


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
