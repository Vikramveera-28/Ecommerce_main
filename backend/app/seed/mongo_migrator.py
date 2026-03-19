from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bson.binary import Binary
from pymongo import MongoClient, ReplaceOne


MIGRATION_META_COLLECTION = "_migration_runs"
BULK_CHUNK_SIZE = 1000


@dataclass
class TableMigrationResult:
    table_name: str
    source_count: int
    target_count: int
    primary_keys: list[str]


def migrate_sqlite_to_mongo(
    *,
    sqlite_path: Path,
    mongo_uri: str,
    db_name: str,
    drop_existing: bool = False,
) -> dict[str, Any]:
    sqlite_path = Path(sqlite_path)
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {sqlite_path}")
    if not mongo_uri.strip():
        raise ValueError("MongoDB URI is required")
    if not db_name.strip():
        raise ValueError("MongoDB database name is required")

    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    client = MongoClient(mongo_uri, appname="EcommerceSQLiteMigration")
    try:
        db = client[db_name]
        table_names = _list_tables(cursor)
        if drop_existing:
            for table_name in table_names:
                db.drop_collection(table_name)
            db.drop_collection(MIGRATION_META_COLLECTION)

        results: list[TableMigrationResult] = []
        for table_name in table_names:
            pk_columns = _primary_key_columns(cursor, table_name)
            rows = cursor.execute(f'SELECT * FROM {_quote_identifier(table_name)}').fetchall()
            source_count = len(rows)
            _write_table_rows(db=db, table_name=table_name, rows=rows, pk_columns=pk_columns)
            target_count = db[table_name].count_documents({})
            if target_count != source_count:
                raise RuntimeError(
                    f"Count mismatch for table '{table_name}': sqlite={source_count}, mongo={target_count}"
                )
            results.append(
                TableMigrationResult(
                    table_name=table_name,
                    source_count=source_count,
                    target_count=target_count,
                    primary_keys=pk_columns,
                )
            )

        migration_summary = {
            "source": {
                "engine": "sqlite",
                "path": str(sqlite_path),
            },
            "target": {
                "engine": "mongodb",
                "database": db_name,
            },
            "drop_existing": drop_existing,
            "migrated_at": datetime.now(timezone.utc),
            "tables": [
                {
                    "table_name": result.table_name,
                    "source_count": result.source_count,
                    "target_count": result.target_count,
                    "primary_keys": result.primary_keys,
                }
                for result in results
            ],
            "total_tables": len(results),
            "total_rows": sum(result.source_count for result in results),
        }
        db[MIGRATION_META_COLLECTION].insert_one(migration_summary)

        return {
            "database": db_name,
            "sqlite_path": str(sqlite_path),
            "tables": migration_summary["tables"],
            "total_tables": migration_summary["total_tables"],
            "total_rows": migration_summary["total_rows"],
        }
    finally:
        conn.close()
        client.close()


def _list_tables(cursor: sqlite3.Cursor) -> list[str]:
    rows = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [row[0] for row in rows]


def _primary_key_columns(cursor: sqlite3.Cursor, table_name: str) -> list[str]:
    rows = cursor.execute(f"PRAGMA table_info({_quote_identifier(table_name)})").fetchall()
    pk_rows = sorted((row for row in rows if row[5]), key=lambda row: row[5])
    return [row[1] for row in pk_rows]


def _quote_identifier(value: str) -> str:
    escaped = value.replace('"', '""')
    return f'"{escaped}"'


def _write_table_rows(*, db, table_name: str, rows: list[sqlite3.Row], pk_columns: list[str]) -> None:
    if not rows:
        return

    collection = db[table_name]
    operations = []
    for row in rows:
        document = _row_to_document(row, pk_columns)
        operations.append(ReplaceOne({"_id": document["_id"]}, document, upsert=True))
        if len(operations) >= BULK_CHUNK_SIZE:
            collection.bulk_write(operations, ordered=False)
            operations = []

    if operations:
        collection.bulk_write(operations, ordered=False)


def _row_to_document(row: sqlite3.Row, pk_columns: list[str]) -> dict[str, Any]:
    document = {key: _normalize_value(row[key]) for key in row.keys()}
    document["_id"] = _document_id(document, pk_columns)
    return document


def _normalize_value(value: Any) -> Any:
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, bytes):
        return Binary(value)
    return value


def _document_id(document: dict[str, Any], pk_columns: list[str]) -> Any:
    if len(pk_columns) == 1:
        key = pk_columns[0]
        if document.get(key) is not None:
            return document[key]

    if len(pk_columns) > 1:
        composite = {key: document.get(key) for key in pk_columns}
        if all(value is not None for value in composite.values()):
            return composite

    if document.get("id") is not None:
        return document["id"]

    stable_payload = json.dumps(document, sort_keys=True, default=str)
    return hashlib.sha256(stable_payload.encode("utf-8")).hexdigest()
