from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

from flask import current_app


def mongo_enabled() -> bool:
    return bool(current_app.config.get("USE_MONGO_ONLY", False))


def get_mongo_db():
    return current_app.extensions.get("mongo_db")


def doc_id(document: dict[str, Any]) -> Any:
    if document.get("id") is not None:
        return document["id"]
    return document.get("_id")


def as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1]
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
    return None


def as_obj(document: dict[str, Any]) -> SimpleNamespace:
    data = dict(document)
    data.pop("_id", None)
    if data.get("id") is None and document.get("_id") is not None:
        data["id"] = document["_id"]
    return SimpleNamespace(**data)


def load_collection(mongo_db, name: str) -> list[SimpleNamespace]:
    if mongo_db is None:
        return []
    return [as_obj(doc) for doc in mongo_db[name].find({})]
