import os
from datetime import timedelta


def _is_production_environment() -> bool:
    env_name = (os.getenv("FLASK_ENV") or os.getenv("ENVIRONMENT") or "").strip().lower()
    return env_name == "production" or os.getenv("RENDER", "").lower() == "true"


def _is_mongo_uri(value: str) -> bool:
    return value.startswith("mongodb://") or value.startswith("mongodb+srv://")


def _use_mongo_only() -> bool:
    if os.getenv("USE_MONGO_ONLY", "").lower() == "true":
        return True
    return _is_mongo_uri(os.getenv("DATABASE_URL", ""))


def _resolved_mongodb_uri() -> str:
    explicit = (os.getenv("MONGODB_URI") or "").strip()
    if explicit:
        return explicit
    db_url = (os.getenv("DATABASE_URL") or "").strip()
    if _is_mongo_uri(db_url):
        return db_url
    return ""


def _normalized_database_url() -> str:
    if _use_mongo_only():
        # SQLAlchemy is not used in mongo-only mode.
        return "sqlite:///:memory:"

    db_url = os.getenv("DATABASE_URL", "sqlite:///ecommerce_app.db")
    # Render and some providers expose postgres:// which SQLAlchemy 2 does not accept.
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    # Prevent accidental local SQLite usage in production deployments.
    if _is_production_environment() and db_url.startswith("sqlite"):
        raise RuntimeError("Production DATABASE_URL must be an external database (not sqlite).")
    return db_url


class Config:
    USE_MONGO_ONLY = _use_mongo_only()
    SQLALCHEMY_DATABASE_URI = _normalized_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MONGODB_URI = _resolved_mongodb_uri()
    MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "ecommerce")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "1440")))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "14")))
    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "200 per hour")
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
