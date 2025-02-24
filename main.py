import os
import logging
from flask import Flask, jsonify, request
from flask_login import LoginManager
from routes import register_routes


# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_app():
    # Create Flask app
    app = Flask(__name__)
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

    # Add session configuration for better security
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes

    # Initialize LoginManager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # Import user loader after app creation
    from models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register auth blueprint
    from blueprints.auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    # Register all other routes
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

    return app

# Create and configure the app
app = create_app()

if __name__ == "__main__":
    # Always serve the app on port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)