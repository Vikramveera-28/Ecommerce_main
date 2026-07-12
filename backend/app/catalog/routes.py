from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from app.common.mongo_utils import doc_id, get_mongo_db, mongo_enabled
from app.models import Category, Product, ProductImage, ProductTagMap, Review, Tag, VendorProfile


catalog_bp = Blueprint("catalog", __name__)


def _mongo_collection(name: str):
    mongo_db = get_mongo_db()
    return mongo_db[name] if mongo_db is not None else None


def _mongo_lookup_map(collection_name: str, key_field: str = "id") -> dict:
    collection = _mongo_collection(collection_name)
    if collection is None:
        return {}
    result = {}
    for document in collection.find({}):
        key = document.get(key_field, document.get("_id"))
        result[key] = document
    return result


def _mongo_serialize_product(product: dict, categories: dict, vendors: dict, images: dict, tags: dict, reviews: dict):
    category_id = product.get("category_id")
    vendor_id = product.get("vendor_id")
    product_id = doc_id(product)

    return {
        "id": product_id,
        "legacy_product_id": product.get("legacy_product_id"),
        "name": product.get("name", ""),
        "description": product.get("description", ""),
        "price": float(product.get("price") or 0),
        "discount_price": float(product.get("discount_price") or 0),
        "rating": round(float(product.get("rating") or 0), 2),
        "stock_quantity": int(product.get("stock_quantity") or 0),
        "sku": product.get("sku", ""),
        "status": product.get("status", ""),
        "approval_status": product.get("approval_status", ""),
        "brand": product.get("brand", ""),
        "availability_status": product.get("availability_status", ""),
        "minimum_order_quantity": int(product.get("minimum_order_quantity") or 0),
        "category": (
            {
                "id": doc_id(categories[category_id]),
                "name": categories[category_id].get("name", ""),
                "slug": categories[category_id].get("slug", ""),
            }
            if category_id in categories
            else None
        ),
        "vendor": (
            {
                "id": doc_id(vendors[vendor_id]),
                "store_name": vendors[vendor_id].get("store_name", ""),
                "store_slug": vendors[vendor_id].get("store_slug", ""),
            }
            if vendor_id in vendors
            else None
        ),
        "thumbnail": product.get("thumbnail"),
        "images": [
            {
                "id": doc_id(image),
                "url": image.get("image_url") or image.get("url"),
                "is_primary": bool(image.get("is_primary", False)),
            }
            for image in images.get(product_id, [])
        ],
        "tags": [tag.get("name", "") for tag in tags.get(product_id, [])],
        "recent_reviews": [
            {
                "id": doc_id(review),
                "customer_id": review.get("customer_id"),
                "rating": review.get("rating"),
                "comment": review.get("comment"),
                "created_at": review.get("created_at").isoformat() if review.get("created_at") else None,
            }
            for review in reviews.get(product_id, [])[:5]
        ],
    }


def _mongo_list_products():
    products_collection = _mongo_collection("products")
    if products_collection is None:
        return []
    return list(products_collection.find({"deleted_at": None}))


def _mongo_documents(collection_name: str):
    collection = _mongo_collection(collection_name)
    if collection is None:
        return []
    return list(collection.find({}))


@catalog_bp.get("/products")
def list_products():
    if mongo_enabled():
        products = _mongo_list_products()
        categories = _mongo_lookup_map("categories")
        vendors = _mongo_lookup_map("vendor_profiles")
        images = {}
        tags = {}
        reviews = {}

        for image in _mongo_documents("product_images"):
            images.setdefault(image.get("product_id"), []).append(image)
        for tag in _mongo_documents("product_tags"):
            tags.setdefault(tag.get("product_id"), []).append(tag)
        for review in _mongo_documents("product_reviews"):
            reviews.setdefault(review.get("product_id"), []).append(review)

        category = (request.args.get("category") or "").strip().lower()
        vendor_id = request.args.get("vendor_id", type=int)
        approval_status = (request.args.get("approval_status") or "").strip().lower()
        q = (request.args.get("q") or "").strip().lower()
        min_price = request.args.get("min_price", type=float)
        max_price = request.args.get("max_price", type=float)
        sort = (request.args.get("sort") or "created_desc").lower()

        def matches(product: dict) -> bool:
            if product.get("deleted_at") is not None:
                return False
            if category:
                category_doc = categories.get(product.get("category_id"))
                if not category_doc:
                    return False
                if category not in str(category_doc.get("slug", "")).lower() and category not in str(category_doc.get("name", "")).lower():
                    return False
            if vendor_id and int(product.get("vendor_id") or 0) != vendor_id:
                return False
            if approval_status and str(product.get("approval_status", "")).lower() != approval_status:
                return False
            if q:
                searchable = " ".join(
                    str(product.get(field, "") or "") for field in ("name", "description", "brand", "sku")
                ).lower()
                if q not in searchable:
                    return False
            price = float(product.get("price") or 0)
            if min_price is not None and price < min_price:
                return False
            if max_price is not None and price > max_price:
                return False
            return True

        filtered = [product for product in products if matches(product)]
        if sort == "price_asc":
            filtered.sort(key=lambda item: float(item.get("price") or 0))
        elif sort == "price_desc":
            filtered.sort(key=lambda item: float(item.get("price") or 0), reverse=True)
        elif sort == "rating_desc":
            filtered.sort(key=lambda item: float(item.get("rating") or 0), reverse=True)
        else:
            filtered.sort(key=lambda item: item.get("created_at") or "", reverse=True)

        page = max(request.args.get("page", type=int, default=1), 1)
        per_page = min(max(request.args.get("per_page", type=int, default=20), 1), 100)
        start = (page - 1) * per_page
        end = start + per_page
        page_items = filtered[start:end]

        return jsonify(
            {
                "items": [_mongo_serialize_product(p, categories, vendors, images, tags, reviews) for p in page_items],
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "pages": (len(filtered) + per_page - 1) // per_page,
                    "total": len(filtered),
                },
            }
        )

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
            "items": [
                {
                    "id": p.id,
                    "legacy_product_id": p.legacy_product_id,
                    "name": p.name,
                    "description": p.description,
                    "price": p.price,
                    "discount_price": p.discount_price,
                    "rating": round(p.rating or 0.0, 2),
                    "stock_quantity": p.stock_quantity,
                    "sku": p.sku,
                    "status": p.status,
                    "approval_status": p.approval_status,
                    "brand": p.brand,
                    "availability_status": p.availability_status,
                    "minimum_order_quantity": p.minimum_order_quantity,
                    "category": {"id": p.category.id, "name": p.category.name, "slug": p.category.slug} if p.category else None,
                    "vendor": {
                        "id": p.vendor.id,
                        "store_name": p.vendor.store_name,
                        "store_slug": p.vendor.store_slug,
                    }
                    if p.vendor
                    else None,
                    "thumbnail": p.thumbnail,
                }
                for p in pagination.items
            ],
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
    if mongo_enabled():
        products_collection = _mongo_collection("products")
        product = products_collection.find_one({"id": product_id}) if products_collection is not None else None
        if not product:
            return jsonify({"error": "Product not found"}), 404
        categories = _mongo_lookup_map("categories")
        vendors = _mongo_lookup_map("vendor_profiles")
        images = {}
        tags = {}
        reviews = {}
        for image in _mongo_documents("product_images"):
            images.setdefault(image.get("product_id"), []).append(image)
        for tag in _mongo_documents("product_tags"):
            tags.setdefault(tag.get("product_id"), []).append(tag)
        for review in _mongo_documents("product_reviews"):
            reviews.setdefault(review.get("product_id"), []).append(review)
        return jsonify(_mongo_serialize_product(product, categories, vendors, images, tags, reviews))

    product = Product.query.filter(Product.id == product_id, Product.deleted_at.is_(None)).first()
    if not product:
        return jsonify({"error": "Product not found"}), 404
    return jsonify(
        {
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
            "category": {"id": product.category.id, "name": product.category.name, "slug": product.category.slug}
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
    )


@catalog_bp.get("/categories")
def list_categories():
    if mongo_enabled():
        collection = _mongo_collection("categories")
        categories = list(collection.find({})) if collection is not None else []
        categories.sort(key=lambda item: str(item.get("name", "")).lower())
        return jsonify(
            [
                {
                    "id": doc_id(category),
                    "name": category.get("name", ""),
                    "slug": category.get("slug", ""),
                    "parent_id": category.get("parent_id"),
                    "status": category.get("status"),
                }
                for category in categories
            ]
        )

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
    if mongo_enabled():
        collection = _mongo_collection("vendor_profiles")
        vendors = list(collection.find({})) if collection is not None else []
        vendors.sort(key=lambda item: str(item.get("store_name", "")).lower())
        return jsonify(
            [
                {
                    "id": doc_id(vendor),
                    "store_name": vendor.get("store_name", ""),
                    "store_slug": vendor.get("store_slug", ""),
                    "kyc_status": vendor.get("kyc_status", ""),
                }
                for vendor in vendors
            ]
        )

    vendors = VendorProfile.query.filter(VendorProfile.deleted_at.is_(None)).order_by(VendorProfile.store_name.asc()).all()
    return jsonify(
        [{"id": v.id, "store_name": v.store_name, "store_slug": v.store_slug, "kyc_status": v.kyc_status} for v in vendors]
    )
