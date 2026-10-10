import os

from dotenv import load_dotenv

# Load environment variables from .env if present (no-op in production)
load_dotenv()

from app import create_app
from app.config import DevelopmentConfig, ProductionConfig

# Use ProductionConfig unless FLASK_DEBUG=1 is explicitly set
debug = os.environ.get("FLASK_DEBUG", "0") == "1"
config_class = DevelopmentConfig if debug else ProductionConfig

app = create_app(config_class)

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "5000")),
        debug=debug,
    )
