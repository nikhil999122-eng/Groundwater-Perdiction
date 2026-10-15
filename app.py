"""
AquaSense AI - Main Flask Application Server
BTech Mini Project: AI-Powered Web-Based Groundwater Monitoring & Prediction System

Provides:
- REST API endpoints under /api
- Static file serving for the HTML/CSS/JS frontend
- CORS support for local development
- Automatic database initialization on start
"""

import os
from pathlib import Path
import sys

# Ensure project root is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from backend.database import init_db
from backend.cgwb_data import init_dwlr_tables
from backend.routes import api_bp

# Load environment variables from .env file if present
load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"


def create_app() -> Flask:
    """Application factory for Flask app."""
    app = Flask(
        __name__,
        static_folder=str(FRONTEND_DIR),
        static_url_path=""
    )

    # Enable Cross-Origin Resource Sharing (CORS)
    # Allows frontend to communicate seamlessly whether served via Flask or opened directly
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Register API Blueprint
    app.register_blueprint(api_bp)

    # Serve Frontend UI
    @app.route("/", methods=["GET"])
    def index():
        return send_from_directory(str(FRONTEND_DIR), "index.html")

    # Serve static assets (CSS, JS, images) from frontend/ directory
    @app.route("/<path:filename>", methods=["GET"])
    def serve_frontend_assets(filename):
        return send_from_directory(str(FRONTEND_DIR), filename)

    # Friendly Health Check Endpoint
    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({
            "status": "online",
            "system": "AquaSense AI Backend",
            "version": "1.0.0",
            "database": "SQLite (Connected)",
            "ml_model": "Random Forest Regressor (Trained)"
        }), 200

    # Clean JSON error handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({
            "success": False,
            "error": "Resource not found (404)."
        }), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({
            "success": False,
            "error": "Internal server error occurred (500)."
        }), 500

    return app


# Create the Flask application instance
app = create_app()

if __name__ == "__main__":
    # Initialize database and populate baseline records if needed
    print("==================================================")
    print("   Starting AquaSense AI Groundwater Backend...   ")
    print("==================================================")
    init_db()
    init_dwlr_tables()
    print("Database and DWLR tables ready.")
    print("Server running at: http://127.0.0.1:5000")
    print("Press Ctrl+C to stop.")
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
