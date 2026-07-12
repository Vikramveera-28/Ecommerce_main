import os
from datetime import timedelta


def _is_mongo_uri(value: str) -> bool:
    return value.startswith("mongodb://") or value.startswith("mongodb+srv://")


def _use_mongo_only() -> bool:
    return True


class Config:
    USE_MONGO_ONLY = _use_mongo_only()
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MONGODB_URI = (os.getenv("MONGODB_URI") or "").strip()
    MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "ecommerce")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "1440")))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "14")))
    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "200 per hour")
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
