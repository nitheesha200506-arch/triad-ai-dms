
from flask import Flask
from flask_cors import CORS
from config import Config

from app.extensions import jwt, init_db

from app.routes.auth import auth
from app.routes.users import users
from app.routes.documents import documents
from app.routes.metadata import metadata
from app.routes.access import access
from app.routes.search import search


def create_app():

    app = Flask(__name__)

    app.config.from_object(Config)

    if not app.config.get("JWT_SECRET_KEY"):
        raise RuntimeError("JWT_SECRET_KEY is missing")

    CORS(app)

    init_db(app)

    jwt.init_app(app)

    app.register_blueprint(
        auth,
        url_prefix="/api/auth"
    )

    app.register_blueprint(
        users,
        url_prefix="/api"
    )

    app.register_blueprint(
        documents,
        url_prefix="/api/documents"
    )

    app.register_blueprint(
        metadata, 
        url_prefix="/api/metadata"
    )

    app.register_blueprint(
        access,
        url_prefix="/api/access"
    )

    app.register_blueprint(
        search,
        url_prefix="/api"
    )

    return app
