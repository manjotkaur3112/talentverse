
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

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    return url


def create_app(test_config=None):
    app = Flask(__name__)

    # CORS: allow the deployed frontend and local development frontend.
    default_origins = [
        "https://acr-talentverse.vercel.app",
        "http://localhost:5173",
    ]

    extra_origins = [
        origin.strip().rstrip("/")
        for origin in os.getenv("FRONTEND_ORIGIN", "").split(",")
        if origin.strip()
    ]

    origins = list(
        dict.fromkeys(default_origins + extra_origins)
    )

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": origins,
            }
        },
        allow_headers=[
            "Content-Type",
            "X-Owner-Id",
        ],
        methods=[
            "GET",
            "POST",
            "PATCH",
            "DELETE",
            "OPTIONS",
        ],
        supports_credentials=False,
    )

    app.config.update(
        SQLALCHEMY_DATABASE_URI=_database_url(),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        RATE_LIMIT_PER_HOUR=int(
            os.getenv("RATE_LIMIT_PER_HOUR", "80")
        ),
        GLOBAL_LIMIT_PER_HOUR=int(
            os.getenv("GLOBAL_LIMIT_PER_HOUR", "400")
        ),
    )

    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    init_limiter(app)

    # Register application API routes.
    routes.register(app)

    # API error handlers.
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
        return jsonify({
            "error": "File is too large (max 5 MB)."
        }), 413

    @app.errorhandler(Exception)
    def on_unexpected(e):
        # Preserve Werkzeug HTTP error status codes.
        if hasattr(e, "code") and isinstance(e.code, int):
            return jsonify({
                "error": getattr(
                    e, "description", "Request failed."
                )
            }), e.code

        app.logger.exception("Unexpected error")

        return jsonify({
            "error": "Something went wrong. Please try again."
        }), 500

    # Root endpoint.
    @app.get("/")
    def root():
        return jsonify({
            "service": "TalentVerse API",
            "status": "ok",
            "note": (
                "This is the backend. "
                "Open the frontend app to use TalentVerse."
            ),
            "health": "/api/health",
        })

    # Health endpoint.
    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        debug=True,
        port=int(os.getenv("PORT", "5000")),
    )
