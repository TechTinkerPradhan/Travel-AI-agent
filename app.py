import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

    # Configure SQLAlchemy
    logger.debug("Configuring database connection...")
    database_url = os.environ.get("DATABASE_URL") 
    logger.info(f"Using database: {database_url}")
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///local.db"
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }

    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    with app.app_context():
        # Import models here to avoid circular imports
        from models import User

        @login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))

        # Register blueprints
        from auth import auth as auth_blueprint
        app.register_blueprint(auth_blueprint)

        # Create database tables
        db.create_all()
        logger.info("Database tables created successfully")

    return app