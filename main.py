import logging
from app import create_app
from flask import jsonify, request
from routes import register_routes

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create and configure the Flask app
app = create_app()
register_routes(app)

# Error handler for 404 (Not Found)
@app.errorhandler(404)
def not_found(e):
    """Return JSON for HTTP 404 errors."""
    logger.error(f"404 error at {request.url}")
    return jsonify({"status": "error", "message": "Resource not found"}), 404

# Global error handler
@app.errorhandler(Exception)
def handle_exception(e):
    """Return JSON instead of HTML for unhandled errors."""
    logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
    return jsonify({"status": "error", "message": "Internal server error"}), 500

if __name__ == "__main__":
    logger.info("Starting Flask server...")
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logger.error(f"Server failed to start: {str(e)}", exc_info=True)
