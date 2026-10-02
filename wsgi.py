import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

from app import create_app
from app.config import DevelopmentConfig, ProductionConfig

env = os.environ.get("FLASK_ENV", "development")
config_class = ProductionConfig if env == "production" else DevelopmentConfig

app = create_app(config_class)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
