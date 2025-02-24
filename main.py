import os
import logging
from flask import Flask, jsonify
from routes import register_routes

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")
# Add session configuration for better security and reliability
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes

# Register error handlers
@app.errorhandler(Exception)
def handle_exception(e):
    """Return JSON instead of HTML for any error"""
    logging.error(f"Unhandled exception: {str(e)}", exc_info=True)
    return jsonify({"status": "error", "message": str(e)}), 500

@app.errorhandler(404)
def not_found(e):
    """Return JSON instead of HTML for HTTP 404"""
    return jsonify({"status": "error", "message": "Resource not found"}), 404

# Register routes
register_routes(app)

if __name__ == "__main__":
    # ALWAYS serve the app on port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)