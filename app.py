import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize SQLAlchemy
db = SQLAlchemy()

def create_app():
    """Initialize and configure the Flask app"""
    app = Flask(__name__)

    # Set a secret key (from environment or fallback)
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

    # Configure SQLAlchemy with database URL
    database_url = os.environ.get("DATABASE_URL", "sqlite:///local.db")
    if not database_url:
        logger.error("DATABASE_URL is not set. Using local SQLite database.")
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize extensions
    db.init_app(app)

    with app.app_context():
        # Import models here
        from models import User

        # Ensure database tables exist
        try:
            db.create_all()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")

    return app