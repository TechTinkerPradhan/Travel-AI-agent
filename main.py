import logging
import os
from flask import Flask, jsonify, request
from routes import register_routes

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create and configure the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET") #Added back in from original
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

if __name__ == "__main__":
    logger.info("Starting Flask server...")
    app.run(host='0.0.0.0', port=5000, debug=True)