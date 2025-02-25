import logging
from app import create_app
from routes import register_routes

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create and configure the app
app = create_app()
register_routes(app)

if __name__ == "__main__":
    logger.info("Starting Flask server...")
    app.run(host='0.0.0.0', port=5000, debug=True)