import os
import logging
from flask import Flask, jsonify, request
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()

def create_app():
    logger.debug("Creating Flask application...")
    app = Flask(__name__)
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

    # Configure SQLAlchemy
    logger.debug("Configuring database...")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }

    # Add session configuration for better security
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes

    # Initialize extensions
    logger.debug("Initializing extensions...")
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    with app.app_context():
        # Import models and create tables
        logger.debug("Creating database tables...")
        from models.user import User
        db.create_all()

        @login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))

        # Register blueprints
        logger.debug("Registering blueprints...")
        from blueprints.auth import auth as auth_blueprint
        app.register_blueprint(auth_blueprint, url_prefix='/auth')

        # Register other routes
        logger.debug("Registering application routes...")
        from routes import register_routes
        register_routes(app)

        # Register error handlers
        @app.errorhandler(404)
        def not_found(e):
            """Return JSON for HTTP 404 errors."""
            logger.error(f"404 error: {request.url}")
            return jsonify({"status": "error", "message": "Resource not found"}), 404

        @app.errorhandler(Exception)
        def handle_exception(e):
            """Return JSON instead of HTML for any error."""
            logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
            return jsonify({"status": "error", "message": str(e)}), 500

        logger.debug("Application setup completed successfully")
        return app

# Create and configure the app
app = create_app()

if __name__ == "__main__":
    logger.info("Starting Flask server...")
    app.run(host='0.0.0.0', port=3000, debug=True)