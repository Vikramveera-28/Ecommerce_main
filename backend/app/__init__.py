from flask import Flask, request

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
from app.vendor_portal.routes import vendor_bp


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)
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

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(_jwt_header, jwt_payload):
        jti = jwt_payload.get("jti")
        return RevokedToken.query.filter_by(jti=jti).first() is not None

    return app
