"""
PDF Converter API — Flask/Render edition
Entry point: registers all blueprints and starts the server.
"""

import logging
import secrets
import sys

from flask import Flask
from routes.health import health_bp
from routes.jobs import jobs_bp
from routes.manipulate import manipulate_bp
from routes.pdf import pdf_bp

logging.basicConfig(level=logging.INFO)


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(health_bp)
    app.register_blueprint(pdf_bp)
    app.register_blueprint(manipulate_bp)
    app.register_blueprint(jobs_bp)
    return app


app = create_app()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "genkey":
        key = secrets.token_urlsafe(32)
        print(f"\nGenerated API key:\n\n  {key}\n")
        print("Set on Render dashboard as:")
        print(f"  PDF_API_KEY = {key}\n")
    else:
        app.run(host="0.0.0.0", port=10000, debug=False)