from __future__ import annotations

import csv
import hashlib
import os
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

import click
from flask import Flask
from sqlalchemy import func

from app.common.utils import looks_like_url, slugify
from app.extensions import db
from app.finance.service import ensure_delivery_ledger_for_shipment
from app.models import (
    AccountStatus,
    Category,
    CustomerProfile,
    DeliveryProfile,
    LogisticsProfile,
    OrderItem,
    Product,
    ProductApprovalStatus,
    ProductImage,
    ProductStatus,
    ProductTagMap,
    Review,
    Role,
    StagingProduct,
    StagingProductImage,
    StagingProductReview,
    StagingProductTag,
    Tag,
    User,
    VendorPayout,
    VendorKycStatus,
    VendorProfile,
    Shipment,
    ShipmentStatus,
)
from app.seed.mongo_migrator import migrate_sqlite_to_mongo

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SOURCE_TABLES = {"products", "product_images", "product_tags", "product_reviews"}


def register_seed_commands(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db_command():
        """Create all configured DB tables."""
        db.create_all()
        click.echo("Database tables created.")

    @app.cli.command("seed-import")
    @click.option("--sqlite-path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
    def seed_import_command(sqlite_path: Path):
        """Import catalog data from sqlite into platform schema with staging + transform."""
        result = run_seed_import(sqlite_path)
        click.echo(result)

    @app.cli.command("export-user-credentials")
    @click.option(
        "--output-path",
        default="user_credentials.csv",
        type=click.Path(dir_okay=False, path_type=Path),
    )
    def export_user_credentials_command(output_path: Path):
        """Export user IDs with known/default passwords into CSV."""
        exported_count = export_user_credentials_csv(output_path)
        click.echo(f"Exported {exported_count} users to {output_path}")

    @app.cli.command("sqlite-to-mongo")
    @click.option(
        "--sqlite-path",
        default=Path(app.instance_path) / "ecommerce_app.db",
        show_default=True,
        type=click.Path(exists=True, dir_okay=False, path_type=Path),
    )
    @click.option("--mongo-uri", default=lambda: os.getenv("MONGODB_URI", ""), show_default=False)
    @click.option("--db-name", default=lambda: os.getenv("MONGODB_DB_NAME", "ecommerce"), show_default=True)
    @click.option("--drop-existing/--keep-existing", default=False, show_default=True)
    def sqlite_to_mongo_command(sqlite_path: Path, mongo_uri: str, db_name: str, drop_existing: bool):
        """Copy every SQLite table into MongoDB collections with count verification."""
        if not mongo_uri.strip():
            raise click.ClickException("MongoDB URI is required. Pass --mongo-uri or set MONGODB_URI.")

        try:
            result = migrate_sqlite_to_mongo(
                sqlite_path=sqlite_path,
                mongo_uri=mongo_uri,
                db_name=db_name,
                drop_existing=drop_existing,
            )
        except Exception as exc:  # noqa: BLE001 - surface a readable CLI error
            raise click.ClickException(str(exc)) from exc

        lines = [
            f"SQLite -> MongoDB migration completed for database '{result['database']}'.",
            f"Source SQLite: {result['sqlite_path']}",
            f"Tables migrated: {result['total_tables']}",
            f"Rows migrated: {result['total_rows']}",
            "Per-table counts:",
        ]
        lines.extend(
            f"- {row['table_name']}: sqlite={row['source_count']}, mongo={row['target_count']}" for row in result["tables"]
        )
        click.echo("\n".join(lines))

    @app.cli.command("finance-backfill-ledger")
    def finance_backfill_ledger_command():
        """Create ledger entries for already-delivered shipments that predate the finance rollout."""
        from app.models import LedgerEntry

        delivered_shipments = (
            Shipment.query.filter(Shipment.shipment_status == ShipmentStatus.DELIVERED.value)
            .order_by(Shipment.id.asc())
            .all()
        )

        before_count = LedgerEntry.query.count()
        shipment_count = 0
        for shipment in delivered_shipments:
            entries = ensure_delivery_ledger_for_shipment(shipment.id)
            if entries:
                shipment_count += 1

        db.session.commit()
        created_count = LedgerEntry.query.count() - before_count
        click.echo(
            f"Finance ledger backfill completed. Delivered shipments processed: {len(delivered_shipments)}. "
            f"Shipments with ledger coverage: {shipment_count}. Newly created entries: {created_count}."
        )


def run_seed_import(sqlite_path: Path) -> str:
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row
    cur = sqlite_conn.cursor()

    table_rows = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    available = {row[0] for row in table_rows}
    missing = SOURCE_TABLES - available
    if missing:
        raise RuntimeError(f"Missing source tables: {sorted(missing)}")

    source_counts = {
        "products": cur.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "product_images": cur.execute("SELECT COUNT(*) FROM product_images").fetchone()[0],
        "product_tags": cur.execute("SELECT COUNT(*) FROM product_tags").fetchone()[0],
        "product_reviews": cur.execute("SELECT COUNT(*) FROM product_reviews").fetchone()[0],
    }

    _load_staging(cur)
    _validate_staging_counts(source_counts)

    warnings = []
    _transform_categories()
    vendor_map, category_vendor_ids = _transform_vendors()
    product_map, product_source_rating = _transform_products(vendor_map)
    _sync_order_item_vendor_links()
    _cleanup_non_category_vendors(category_vendor_ids)
    warnings.extend(_transform_images(product_map))
    _transform_tags(product_map)
    _transform_reviews(product_map)
    _normalize_product_ratings(product_source_rating)
    _ensure_default_admin()
    _ensure_default_logistics()
    _ensure_default_delivery_boy()

    db.session.commit()
    sqlite_conn.close()

    warnings_text = ""
    if warnings:
        warnings_text = "\nWarnings:\n- " + "\n- ".join(warnings)

    return (
        "Seed import completed successfully.\n"
        f"Source counts: {source_counts}\n"
        f"Imported products: {Product.query.count()}, categories: {Category.query.count()}, vendors: {VendorProfile.query.count()}"
        f"{warnings_text}"
    )


def _load_staging(cur: sqlite3.Cursor) -> None:
    # Reset staging to make the command deterministic and idempotent.
    StagingProductReview.query.delete()
    StagingProductTag.query.delete()
    StagingProductImage.query.delete()
    StagingProduct.query.delete()
    db.session.flush()

    products = cur.execute("SELECT * FROM products").fetchall()
    for row in products:
        db.session.add(
            StagingProduct(
                source_id=row["id"],
                title=row["title"],
                description=row["description"],
                category=row["category"],
                price=row["price"],
                discount_percentage=row["discount_percentage"],
                rating=row["rating"],
                stock=row["stock"],
                brand=row["brand"],
                sku=row["sku"],
                weight=row["weight"],
                dim_width=row["dim_width"],
                dim_height=row["dim_height"],
                dim_depth=row["dim_depth"],
                warranty_information=row["warranty_information"],
                shipping_information=row["shipping_information"],
                availability_status=row["availability_status"],
                return_policy=row["return_policy"],
                minimum_order_quantity=row["minimum_order_quantity"],
                meta_created_at=row["meta_created_at"],
                meta_updated_at=row["meta_updated_at"],
                barcode=row["barcode"],
                qr_code=row["qr_code"],
                thumbnail=row["thumbnail"],
            )
        )

    images = cur.execute("SELECT * FROM product_images").fetchall()
    for row in images:
        db.session.add(StagingProductImage(source_id=row["id"], product_id=row["product_id"], image_url=row["image_url"]))

    tags = cur.execute("SELECT * FROM product_tags").fetchall()
    for row in tags:
        db.session.add(StagingProductTag(source_id=row["id"], product_id=row["product_id"], tag=row["tag"]))

    reviews = cur.execute("SELECT * FROM product_reviews").fetchall()
    for row in reviews:
        db.session.add(
            StagingProductReview(
                source_id=row["id"],
                product_id=row["product_id"],
                rating=row["rating"],
                comment=row["comment"],
                review_date=row["date"],
                reviewer_name=row["reviewer_name"],
                reviewer_email=row["reviewer_email"],
            )
        )

    db.session.commit()


def _validate_staging_counts(source_counts: dict) -> None:
    staging_counts = {
        "products": StagingProduct.query.count(),
        "product_images": StagingProductImage.query.count(),
        "product_tags": StagingProductTag.query.count(),
        "product_reviews": StagingProductReview.query.count(),
    }
    for key, count in source_counts.items():
        if staging_counts[key] != count:
            raise RuntimeError(f"Staging mismatch for {key}: source={count}, staging={staging_counts[key]}")


def _transform_categories() -> None:
    categories = db.session.query(StagingProduct.category).distinct().all()
    for (raw_category,) in categories:
        title = (raw_category or "uncategorized").strip()
        slug = slugify(title)

        category = Category.query.filter_by(slug=slug).first()
        if not category:
            category = Category(name=title.replace("-", " ").title(), slug=slug, status=ProductStatus.ACTIVE.value)
            db.session.add(category)

    db.session.flush()


def _safe_email(base: str, domain: str = "seed.local") -> str:
    slug = slugify(base).replace("-", "")
    if not slug:
        slug = hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()[:10]
    digest = hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()[:6]
    return f"{slug}.{digest}@{domain}"


def _ensure_vendor_user(store_name: str) -> User:
    email = _safe_email(f"vendor-{store_name}")
    user = User.query.filter_by(email=email).first()
    if user:
        _activate_vendor_user(user)
        return user

    user = User(
        name=f"{store_name} Owner",
        email=email,
        role=Role.VENDOR.value,
        status=AccountStatus.ACTIVE.value,
        email_verified=True,
    )
    user.set_password("vendor12345")
    db.session.add(user)
    db.session.flush()
    return user


def _activate_vendor_user(user: User) -> None:
    user.role = Role.VENDOR.value
    user.status = AccountStatus.ACTIVE.value
    user.email_verified = True


def _transform_vendors() -> tuple[dict[str, int], set[int]]:
    categories = Category.query.order_by(Category.id.asc()).all()

    vendor_map: dict[str, int] = {}
    category_vendor_ids: set[int] = set()
    for category in categories:
        category_slug = slugify(category.slug or category.name or "uncategorized")
        category_name = (category.name or "Uncategorized").strip()
        store_name = f"{category_name} Vendor"
        store_slug = slugify(f"{category_slug}-vendor")
        vendor = VendorProfile.query.filter_by(store_slug=store_slug).first()
        if vendor:
            linked_user = User.query.get(vendor.user_id)
            if linked_user:
                _activate_vendor_user(linked_user)
        else:
            user = _ensure_vendor_user(store_name)
            vendor = VendorProfile(
                user_id=user.id,
                store_name=store_name,
                store_slug=store_slug,
                kyc_status=VendorKycStatus.APPROVED.value,
                total_rating=0.0,
            )
            db.session.add(vendor)
            db.session.flush()

        vendor.store_name = store_name
        vendor.kyc_status = VendorKycStatus.APPROVED.value
        vendor.total_rating = float(vendor.total_rating or 0.0)
        vendor_map[category_slug] = vendor.id
        category_vendor_ids.add(vendor.id)

    return vendor_map, category_vendor_ids


def _transform_products(vendor_map: dict[str, int]):
    rows = StagingProduct.query.order_by(StagingProduct.source_id.asc()).all()
    category_map = {c.slug: c for c in Category.query.all()}

    product_map: dict[int, int] = {}
    source_rating: dict[int, float] = {}

    for row in rows:
        category_slug = slugify(row.category or "uncategorized")
        category = category_map.get(category_slug)
        if not category:
            raise RuntimeError(f"Category missing during transform: {category_slug}")

        vendor_id = vendor_map[category_slug]
        discount_price = None
        if row.discount_percentage and row.price is not None:
            discount_price = round(float(row.price) * (1 - float(row.discount_percentage) / 100.0), 2)

        product = Product.query.filter_by(legacy_product_id=row.source_id).first()
        if not product and row.sku:
            product = Product.query.filter_by(sku=row.sku).first()

        if not product:
            product = Product(
                legacy_product_id=row.source_id,
                vendor_id=vendor_id,
                category_id=category.id,
                name=row.title or f"Product {row.source_id}",
                sku=row.sku or f"legacy-sku-{row.source_id}",
                price=float(row.price or 0.0),
                discount_price=discount_price,
                stock_quantity=int(row.stock or 0),
                description=row.description,
                status=ProductStatus.ACTIVE.value,
                approval_status=ProductApprovalStatus.APPROVED.value,
                brand=row.brand,
                weight=row.weight,
                dim_width=row.dim_width,
                dim_height=row.dim_height,
                dim_depth=row.dim_depth,
                warranty_information=row.warranty_information,
                shipping_information=row.shipping_information,
                availability_status=row.availability_status,
                return_policy=row.return_policy,
                minimum_order_quantity=row.minimum_order_quantity,
                barcode=row.barcode,
                qr_code=row.qr_code,
                thumbnail=row.thumbnail,
                rating=float(row.rating or 0.0),
            )
            db.session.add(product)
            db.session.flush()
        else:
            product.legacy_product_id = row.source_id
            product.vendor_id = vendor_id
            product.category_id = category.id
            product.name = row.title or product.name
            product.description = row.description
            product.price = float(row.price or 0.0)
            product.discount_price = discount_price
            product.stock_quantity = int(row.stock or 0)
            product.brand = row.brand
            product.weight = row.weight
            product.dim_width = row.dim_width
            product.dim_height = row.dim_height
            product.dim_depth = row.dim_depth
            product.warranty_information = row.warranty_information
            product.shipping_information = row.shipping_information
            product.availability_status = row.availability_status
            product.return_policy = row.return_policy
            product.minimum_order_quantity = row.minimum_order_quantity
            product.barcode = row.barcode
            product.qr_code = row.qr_code
            product.thumbnail = row.thumbnail
            product.status = ProductStatus.ACTIVE.value
            product.approval_status = ProductApprovalStatus.APPROVED.value

        product_map[row.source_id] = product.id
        source_rating[product.id] = float(row.rating or 0.0)

    duplicates = (
        db.session.query(Product.sku, func.count(Product.id).label("cnt"))
        .group_by(Product.sku)
        .having(func.count(Product.id) > 1)
        .all()
    )
    if duplicates:
        raise RuntimeError(f"Duplicate SKU detected: {duplicates[:3]}")

    if len(product_map) != StagingProduct.query.count():
        raise RuntimeError("Product count mismatch during transform")

    db.session.flush()
    return product_map, source_rating


def _sync_order_item_vendor_links() -> None:
    rows = (
        db.session.query(OrderItem, Product.vendor_id)
        .join(Product, Product.id == OrderItem.product_id)
        .all()
    )
    for order_item, target_vendor_id in rows:
        if order_item.vendor_id != target_vendor_id:
            order_item.vendor_id = target_vendor_id


def _cleanup_non_category_vendors(category_vendor_ids: set[int]) -> None:
    if not category_vendor_ids:
        return

    protected_vendor_ids = set(category_vendor_ids)
    protected_vendor_ids.update(vendor_id for (vendor_id,) in db.session.query(Product.vendor_id).distinct().all() if vendor_id)
    protected_vendor_ids.update(vendor_id for (vendor_id,) in db.session.query(OrderItem.vendor_id).distinct().all() if vendor_id)
    protected_vendor_ids.update(vendor_id for (vendor_id,) in db.session.query(VendorPayout.vendor_id).distinct().all() if vendor_id)

    stale_vendors = VendorProfile.query.filter(~VendorProfile.id.in_(protected_vendor_ids)).all()
    stale_user_ids = [vendor.user_id for vendor in stale_vendors]
    for vendor in stale_vendors:
        db.session.delete(vendor)
    db.session.flush()

    if stale_user_ids:
        for user in User.query.filter(User.id.in_(stale_user_ids)).all():
            has_profile = VendorProfile.query.filter_by(user_id=user.id).first() is not None
            if user.role == Role.VENDOR.value and not has_profile:
                user.role = Role.CUSTOMER.value


def _transform_images(product_map: dict[int, int]) -> list[str]:
    warnings: list[str] = []
    grouped: dict[int, set[str]] = defaultdict(set)

    for row in StagingProductImage.query.order_by(StagingProductImage.source_id.asc()).all():
        if row.product_id not in product_map:
            continue
        if not looks_like_url(row.image_url):
            warnings.append(f"Malformed image URL for source image id {row.source_id}")
            continue
        grouped[row.product_id].add(row.image_url.strip())

    for row in StagingProduct.query.all():
        if row.thumbnail:
            if looks_like_url(row.thumbnail):
                grouped[row.source_id].add(row.thumbnail.strip())
            else:
                warnings.append(f"Malformed thumbnail URL for source product id {row.source_id}")
        if row.qr_code and not looks_like_url(row.qr_code):
            warnings.append(f"Malformed qr_code URL for source product id {row.source_id}")

    for source_product_id, urls in grouped.items():
        target_product_id = product_map[source_product_id]
        ProductImage.query.filter_by(product_id=target_product_id).delete()

        sorted_urls = sorted(urls)
        for idx, url in enumerate(sorted_urls):
            db.session.add(ProductImage(product_id=target_product_id, image_url=url, is_primary=idx == 0))

    return warnings


def _normalize_tag(tag: str) -> str:
    return " ".join((tag or "").strip().lower().split())


def _transform_tags(product_map: dict[int, int]) -> None:
    grouped: dict[int, set[str]] = defaultdict(set)
    for row in StagingProductTag.query.all():
        clean = _normalize_tag(row.tag)
        if clean:
            grouped[row.product_id].add(clean)

    for source_product_id, tags in grouped.items():
        target_product_id = product_map.get(source_product_id)
        if not target_product_id:
            continue

        ProductTagMap.query.filter_by(product_id=target_product_id).delete()

        for tag_name in sorted(tags):
            tag = Tag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                db.session.add(tag)
                db.session.flush()

            db.session.add(ProductTagMap(product_id=target_product_id, tag_id=tag.id))


def _sanitize_reviewer_email(raw_email: str, reviewer_name: str) -> str:
    raw_email = (raw_email or "").strip().lower()
    if raw_email and EMAIL_PATTERN.match(raw_email):
        return raw_email

    fallback_base = reviewer_name or raw_email or "reviewer"
    digest = hashlib.sha1(fallback_base.encode("utf-8", errors="ignore")).hexdigest()[:10]
    return f"seed+{digest}@local"


def _ensure_seed_customer_user(email: str, name: str | None) -> User:
    user = User.query.filter_by(email=email).first()
    if user:
        return user

    user = User(
        name=(name or email.split("@")[0]).strip()[:120] or "Seed Customer",
        email=email,
        role=Role.CUSTOMER.value,
        status=AccountStatus.ACTIVE.value,
        email_verified=True,
    )
    user.set_password("customer12345")
    db.session.add(user)
    db.session.flush()

    profile = CustomerProfile.query.filter_by(user_id=user.id).first()
    if not profile:
        db.session.add(CustomerProfile(user_id=user.id))

    return user


def _transform_reviews(product_map: dict[int, int]) -> None:
    # Keep import idempotent by recreating review rows from source.
    target_product_ids = list(product_map.values())
    if target_product_ids:
        Review.query.filter(Review.product_id.in_(target_product_ids)).delete(synchronize_session=False)

    reviews = StagingProductReview.query.order_by(StagingProductReview.source_id.asc()).all()
    for row in reviews:
        target_product_id = product_map.get(row.product_id)
        if not target_product_id:
            continue

        email = _sanitize_reviewer_email(row.reviewer_email, row.reviewer_name)
        customer = _ensure_seed_customer_user(email=email, name=row.reviewer_name)

        rating = float(row.rating or 0.0)
        rating = max(0.0, min(rating, 5.0))

        db.session.add(
            Review(
                product_id=target_product_id,
                customer_id=customer.id,
                rating=rating,
                comment=row.comment,
            )
        )


def _normalize_product_ratings(source_rating: dict[int, float]) -> None:
    products = Product.query.all()
    for product in products:
        avg_rating = db.session.query(func.avg(Review.rating)).filter(Review.product_id == product.id).scalar()
        if avg_rating is not None:
            product.rating = round(float(avg_rating), 2)
        else:
            product.rating = round(float(source_rating.get(product.id, 0.0)), 2)


def _ensure_default_admin() -> None:
    admin_email = os.getenv("SEED_ADMIN_EMAIL", "admin@seed.local").strip().lower()
    admin_password = os.getenv("SEED_ADMIN_PASSWORD", "admin12345")
    existing = User.query.filter_by(email=admin_email).first()
    if existing:
        if existing.role != Role.ADMIN.value:
            existing.role = Role.ADMIN.value
        if existing.status != AccountStatus.ACTIVE.value:
            existing.status = AccountStatus.ACTIVE.value
        return

    admin = User(
        name="Seed Admin",
        email=admin_email,
        role=Role.ADMIN.value,
        status=AccountStatus.ACTIVE.value,
        email_verified=True,
    )
    admin.set_password(admin_password)
    db.session.add(admin)


def _ensure_default_logistics() -> None:
    logistics_email = os.getenv("SEED_LOGISTICS_EMAIL", "logistics@seed.local").strip().lower()
    logistics_password = os.getenv("SEED_LOGISTICS_PASSWORD", "logistics12345")
    existing = User.query.filter_by(email=logistics_email).first()
    if existing:
        if existing.role != Role.LOGISTICS.value:
            existing.role = Role.LOGISTICS.value
        if existing.status != AccountStatus.ACTIVE.value:
            existing.status = AccountStatus.ACTIVE.value
        profile = LogisticsProfile.query.filter_by(user_id=existing.id).first()
        if not profile:
            db.session.add(LogisticsProfile(user_id=existing.id, status=AccountStatus.ACTIVE.value, service_area="Default"))
        return

    logistics = User(
        name="Seed Logistics",
        email=logistics_email,
        role=Role.LOGISTICS.value,
        status=AccountStatus.ACTIVE.value,
        email_verified=True,
    )
    logistics.set_password(logistics_password)
    db.session.add(logistics)
    db.session.flush()
    db.session.add(LogisticsProfile(user_id=logistics.id, status=AccountStatus.ACTIVE.value, service_area="Default"))


def _ensure_default_delivery_boy() -> None:
    delivery_email = os.getenv("SEED_DELIVERY_BOY_EMAIL", "delivery@seed.local").strip().lower()
    delivery_password = os.getenv("SEED_DELIVERY_BOY_PASSWORD", "delivery12345")
    existing = User.query.filter_by(email=delivery_email).first()
    if existing:
        if existing.role != Role.DELIVERY_BOY.value:
            existing.role = Role.DELIVERY_BOY.value
        if existing.status != AccountStatus.ACTIVE.value:
            existing.status = AccountStatus.ACTIVE.value
        profile = DeliveryProfile.query.filter_by(user_id=existing.id).first()
        if not profile:
            db.session.add(DeliveryProfile(user_id=existing.id, is_active=True))
        return

    delivery_user = User(
        name="Seed Delivery",
        email=delivery_email,
        role=Role.DELIVERY_BOY.value,
        status=AccountStatus.ACTIVE.value,
        email_verified=True,
    )
    delivery_user.set_password(delivery_password)
    db.session.add(delivery_user)
    db.session.flush()
    db.session.add(DeliveryProfile(user_id=delivery_user.id, is_active=True))


def _detect_known_password(user: User) -> str:
    candidate_passwords_by_role = {
        Role.ADMIN.value: ("admin12345",),
        Role.LOGISTICS.value: ("logistics12345",),
        Role.DELIVERY_BOY.value: ("delivery12345",),
        Role.VENDOR.value: ("vendor12345",),
        Role.CUSTOMER.value: ("customer12345", "pass12345", "vendor12345"),
    }
    for candidate in candidate_passwords_by_role.get(user.role, ()):
        if user.check_password(candidate):
            return candidate
    return "UNKNOWN"


def export_user_credentials_csv(output_path: Path) -> int:
    users = User.query.order_by(User.role.asc(), User.id.asc()).all()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["user_id", "name", "email", "role", "status", "password"])
        for user in users:
            writer.writerow([user.id, user.name, user.email, user.role, user.status, _detect_known_password(user)])

    return len(users)
