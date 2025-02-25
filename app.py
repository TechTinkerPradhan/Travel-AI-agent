import os
import logging
from flask import Flask
from extensions import db, login_manager

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

    # Configure SQLAlchemy with SQLite fallback
    logger.debug("Configuring database connection...")
    database_url = os.environ.get("DATABASE_URL") or "sqlite:///local.db"
    logger.info(f"Using database: {database_url}")
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        # Import User model here to avoid circular imports
        from models.user import User
        return User.query.get(int(user_id))

    # Register blueprints
    from blueprints.auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    # Create database tables
    with app.app_context():
        from models.user import User  # Import here after db is set up
        db.create_all()

    return app