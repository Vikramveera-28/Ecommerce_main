from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from app.models import Category, Product, ProductImage, ProductTagMap, Review, Tag, VendorProfile


catalog_bp = Blueprint("catalog", __name__)


def _serialize_product(product: Product, include_details: bool = False):
    base = {
        "id": product.id,
        "legacy_product_id": product.legacy_product_id,
        "name": product.name,
        "description": product.description,
        "price": product.price,
        "discount_price": product.discount_price,
        "rating": round(product.rating or 0.0, 2),
        "stock_quantity": product.stock_quantity,
        "sku": product.sku,
        "status": product.status,
        "approval_status": product.approval_status,
        "brand": product.brand,
        "availability_status": product.availability_status,
        "minimum_order_quantity": product.minimum_order_quantity,
        "category": {
            "id": product.category.id,
            "name": product.category.name,
            "slug": product.category.slug,
        }
        if product.category
        else None,
        "vendor": {
            "id": product.vendor.id,
            "store_name": product.vendor.store_name,
            "store_slug": product.vendor.store_slug,
        }
        if product.vendor
        else None,
        "thumbnail": product.thumbnail,
    }
    if include_details:
        images = ProductImage.query.filter_by(product_id=product.id).order_by(ProductImage.id.asc()).all()
        tags = (
            Tag.query.join(ProductTagMap, ProductTagMap.tag_id == Tag.id)
            .filter(ProductTagMap.product_id == product.id)
            .order_by(Tag.name.asc())
            .all()
        )
        reviews = Review.query.filter_by(product_id=product.id).order_by(Review.created_at.desc()).limit(5).all()

        base["images"] = [{"id": i.id, "url": i.image_url, "is_primary": i.is_primary} for i in images]
        base["tags"] = [t.name for t in tags]
        base["recent_reviews"] = [
            {"id": r.id, "customer_id": r.customer_id, "rating": r.rating, "comment": r.comment, "created_at": r.created_at.isoformat()}
            for r in reviews
        ]
    return base


@catalog_bp.get("/products")
def list_products():
    query = Product.query.filter(Product.deleted_at.is_(None))

    category = request.args.get("category")
    vendor_id = request.args.get("vendor_id", type=int)
    approval_status = (request.args.get("approval_status") or "").strip().lower()
    q = (request.args.get("q") or "").strip()
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    sort = (request.args.get("sort") or "created_desc").lower()

    if category:
        query = query.join(Category).filter(or_(Category.slug == category, Category.name.ilike(f"%{category}%")))
    if vendor_id:
        query = query.filter(Product.vendor_id == vendor_id)
    if approval_status:
        query = query.filter(Product.approval_status == approval_status)
    if q:
        query = query.filter(
            or_(
                Product.name.ilike(f"%{q}%"),
                Product.description.ilike(f"%{q}%"),
                Product.brand.ilike(f"%{q}%"),
                Product.sku.ilike(f"%{q}%"),
            )
        )
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    if sort == "price_asc":
        query = query.order_by(Product.price.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price.desc())
    elif sort == "rating_desc":
        query = query.order_by(Product.rating.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    page = max(request.args.get("page", type=int, default=1), 1)
    per_page = min(max(request.args.get("per_page", type=int, default=20), 1), 100)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify(
        {
            "items": [_serialize_product(p) for p in pagination.items],
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "pages": pagination.pages,
                "total": pagination.total,
            },
        }
    )


@catalog_bp.get("/products/<int:product_id>")
def get_product(product_id: int):
    product = Product.query.filter(Product.id == product_id, Product.deleted_at.is_(None)).first()
    if not product:
        return jsonify({"error": "Product not found"}), 404
    return jsonify(_serialize_product(product, include_details=True))


@catalog_bp.get("/categories")
def list_categories():
    categories = Category.query.filter(Category.deleted_at.is_(None)).order_by(Category.name.asc()).all()
    return jsonify(
        [
            {
                "id": c.id,
                "name": c.name,
                "slug": c.slug,
                "parent_id": c.parent_id,
                "status": c.status,
            }
            for c in categories
        ]
    )


@catalog_bp.get("/search")
def search_products():
    return list_products()


@catalog_bp.get("/vendors")
def list_vendors():
    vendors = VendorProfile.query.filter(VendorProfile.deleted_at.is_(None)).order_by(VendorProfile.store_name.asc()).all()
    return jsonify(
        [{"id": v.id, "store_name": v.store_name, "store_slug": v.store_slug, "kyc_status": v.kyc_status} for v in vendors]
    )
