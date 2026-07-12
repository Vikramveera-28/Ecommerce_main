import os

from flask import Flask, request, send_from_directory
from pymongo import MongoClient

from app.admin.routes import admin_bp
from app.auth.routes import auth_bp
from app.cart_wishlist.routes import cart_bp
from app.catalog.routes import catalog_bp
from app.config import Config
from app.delivery.routes import delivery_bp
from app.extensions import cors, db, jwt, limiter, migrate
from app.finance.routes import finance_bp
from app.logistics.routes import logistics_bp
from app.models import RevokedToken
from app.orders.routes import orders_bp
from app.seed.importer import register_seed_commands
from app.seed.mongo_defaults import try_ensure_mongo_default_users
from app.vendor_portal.routes import vendor_bp
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")


def create_app(config_object=Config):
    app = Flask(
        __name__,
        static_folder=FRONTEND_DIST,
        static_url_path="/",
    )
    app.config.from_object(config_object)

    use_mongo_only = app.config.get("USE_MONGO_ONLY", False)

    if not use_mongo_only:
        db.init_app(app)
        migrate.init_app(app, db)
    else:
        mongo_uri = app.config.get("MONGODB_URI", "")
        mongo_db_name = app.config.get("MONGODB_DB_NAME", "ecommerce")
        if not mongo_uri:
            raise RuntimeError("MONGODB_URI must be set when USE_MONGO_ONLY is enabled.")
        # connect=False: defer SRV lookup until first use so Gunicorn can bind $PORT on Render.
        mongo_client = MongoClient(
            mongo_uri,
            appname="EcommerceApp",
            connect=False,
            serverSelectionTimeoutMS=5000,
        )
        app.extensions["mongo_client"] = mongo_client
        app.extensions["mongo_db"] = mongo_client[mongo_db_name]
        try_ensure_mongo_default_users(app.extensions["mongo_db"], app.logger)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    limiter.init_app(app)

    @limiter.request_filter
    def _skip_preflight_limits():
        # Avoid rate-limiting CORS preflight requests.
        return request.method == "OPTIONS"

    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(catalog_bp, url_prefix="/api/v1")
    app.register_blueprint(cart_bp, url_prefix="/api/v1")
    app.register_blueprint(orders_bp, url_prefix="/api/v1")
    app.register_blueprint(vendor_bp, url_prefix="/api/v1/vendor")
    app.register_blueprint(logistics_bp, url_prefix="/api/v1/logistics")
    app.register_blueprint(delivery_bp, url_prefix="/api/v1/delivery")
    app.register_blueprint(admin_bp, url_prefix="/api/v1/admin")
    app.register_blueprint(finance_bp, url_prefix="/api/v1/finance")

    register_seed_commands(app)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        if path and os.path.exists(os.path.join(FRONTEND_DIST, path)):
            return send_from_directory(FRONTEND_DIST, path)
        return send_from_directory(FRONTEND_DIST, "index.html")

    @app.get("/health")
    def health_check():
        payload = {"status": "ok"}
        if app.config.get("USE_MONGO_ONLY", False):
            mongo_client = app.extensions.get("mongo_client")
            try:
                mongo_client.admin.command("ping")
                payload["mongo"] = "ok"
            except Exception as exc:
                payload["status"] = "degraded"
                payload["mongo"] = "error"
                payload["mongo_error"] = str(exc)
        return payload

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(_jwt_header, jwt_payload):
        jti = jwt_payload.get("jti")
        if app.config.get("USE_MONGO_ONLY", False):
            mongo_db = app.extensions.get("mongo_db")
            if not mongo_db:
                return False
            return mongo_db["revoked_tokens"].find_one({"jti": jti}) is not None
        return RevokedToken.query.filter_by(jti=jti).first() is not None

    return app
