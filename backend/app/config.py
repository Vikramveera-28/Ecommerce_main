import os
from datetime import timedelta


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
        return "sqlite:///:memory:"

    db_url = os.getenv("DATABASE_URL", "sqlite:///ecommerce_app.db")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return db_url


class Config:
    USE_MONGO_ONLY = _use_mongo_only()
    SQLALCHEMY_DATABASE_URI = _normalized_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MONGODB_URI = _resolved_mongodb_uri()
    MONGODB_DB_NAME = os.getenv("MONGODB_DB") or os.getenv("MONGODB_DB_NAME", "ecommerce")
    JWT_SECRET_KEY = os.getenv("AUTH_SECRET") or os.getenv("JWT_SECRET_KEY", "change-this-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "1440")))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "14")))
    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "200 per hour")
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
