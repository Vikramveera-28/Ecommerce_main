from __future__ import annotations

import os
from datetime import datetime, timezone

from pymongo.errors import PyMongoError
from werkzeug.security import generate_password_hash

from app.models import AccountStatus, Role


def _upsert_user(users, *, email: str, password: str, name: str, role: str) -> bool:
    now = datetime.now(timezone.utc)
    existing = users.find_one({"email": email})
    if existing:
        users.update_one(
            {"email": email},
            {
                "$set": {
                    "role": role,
                    "status": AccountStatus.ACTIVE.value,
                    "updated_at": now,
                }
            },
        )
        return False

    users.insert_one(
        {
            "name": name,
            "email": email,
            "password_hash": generate_password_hash(password),
            "role": role,
            "status": AccountStatus.ACTIVE.value,
            "email_verified": True,
            "created_at": now,
            "updated_at": now,
        }
    )
    return True


def ensure_mongo_default_users(mongo_db) -> list[str]:
    """Create default seed users in MongoDB when missing."""
    users = mongo_db["users"]
    created: list[str] = []

    specs = [
        (
            os.getenv("SEED_ADMIN_EMAIL", "admin@seed.local").strip().lower(),
            os.getenv("SEED_ADMIN_PASSWORD", "admin12345"),
            "Seed Admin",
            Role.ADMIN.value,
        ),
        (
            os.getenv("SEED_LOGISTICS_EMAIL", "logistics@seed.local").strip().lower(),
            os.getenv("SEED_LOGISTICS_PASSWORD", "logistics12345"),
            "Seed Logistics",
            Role.LOGISTICS.value,
        ),
        (
            os.getenv("SEED_DELIVERY_BOY_EMAIL", "delivery@seed.local").strip().lower(),
            os.getenv("SEED_DELIVERY_BOY_PASSWORD", "delivery12345"),
            "Seed Delivery",
            Role.DELIVERY_BOY.value,
        ),
    ]

    for email, password, name, role in specs:
        if not email or not password:
            continue
        if _upsert_user(users, email=email, password=password, name=name, role=role):
            created.append(email)

    return created


def try_ensure_mongo_default_users(mongo_db, logger) -> None:
    try:
        created = ensure_mongo_default_users(mongo_db)
        if created:
            logger.info("Created MongoDB seed users: %s", ", ".join(created))
    except PyMongoError as exc:
        logger.warning("Could not ensure MongoDB seed users: %s", exc)
