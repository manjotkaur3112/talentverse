"""TalentVerse API: resume -> structured profile, plus a career workspace built on saved data."""
import logging
import os

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS

load_dotenv()
logging.basicConfig(level=logging.INFO)

import ai
import extractor
import routes
from core import ApiError, init_limiter
from models import db
from services import NotFound


def _database_url():
    url = os.getenv("DATABASE_URL", "sqlite:///talentverse.db")
    if url.startswith("postgres://"):  # Render/Heroku style
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def create_app(test_config=None):
    app = Flask(__name__)
    from flask_cors import CORS

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": [
                    "https://acr-talentverse.vercel.app"
                ]
            }
        },
        allow_headers=["Content-Type", "X-Owner-Id"],
        methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    )
    app.config.update(
        SQLALCHEMY_DATABASE_URI=_database_url(),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        RATE_LIMIT_PER_HOUR=int(os.getenv("RATE_LIMIT_PER_HOUR", "80")),
        GLOBAL_LIMIT_PER_HOUR=int(os.getenv("GLOBAL_LIMIT_PER_HOUR", "400")),
    )
    if test_config:
        app.config.update(test_config)

    origins = [o.strip() for o in os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").split(",") if o.strip()]
    CORS(app, origins=origins, allow_headers=["Content-Type", "X-Owner-Id"],
         methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"])
    db.init_app(app)
    with app.app_context():
        db.create_all()
    init_limiter(app)
    routes.register(app)

    @app.errorhandler(ApiError)
    def on_api_error(e):
        body = {"error": e.message}
        if e.details:
            body["details"] = e.details
        return jsonify(body), e.status

    @app.errorhandler(extractor.InputError)
    def on_input_error(e):
        return jsonify({"error": str(e)}), 422

    @app.errorhandler(ai.AIError)
    def on_ai_error(e):
        return jsonify({"error": str(e)}), 502

    @app.errorhandler(NotFound)
    def on_not_found(e):
        return jsonify({"error": str(e)}), 404

    @app.errorhandler(413)
    def on_too_large(_):
        return jsonify({"error": "File is too large (max 5 MB)."}), 413

    @app.errorhandler(Exception)
    def on_unexpected(e):
        if hasattr(e, "code") and isinstance(e.code, int):  # werkzeug HTTP errors
            return jsonify({"error": getattr(e, "description", "Request failed.")}), e.code
        app.logger.exception("Unexpected error")  # never log resume text
        return jsonify({"error": "Something went wrong. Please try again."}), 500

    @app.get("/")
    def root():
        return jsonify({"service": "TalentVerse API", "status": "ok",
                        "note": "This is the backend. Open the frontend app to use TalentVerse.",
                        "health": "/api/health"})

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", "5000")))
