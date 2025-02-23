import os
import logging
from flask import Flask
from routes import register_routes

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Register routes
register_routes(app)

if __name__ == "__main__":
    # ALWAYS serve the app on port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)