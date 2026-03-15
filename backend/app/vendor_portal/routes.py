from flask import Blueprint, jsonify, request

from app.common.authz import current_user, role_required
from app.common.utils import slugify
from app.extensions import db
from app.models import (
    Category,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductApprovalStatus,
    ProductStatus,
    Role,
    VendorKycStatus,
    VendorProfile,
)


vendor_bp = Blueprint("vendor", __name__)


VALID_VENDOR_ORDER_STATUS = {
    OrderStatus.CONFIRMED.value,
    OrderStatus.PACKED.value,
    OrderStatus.SHIPPED.value,
    OrderStatus.CANCELLED.value,
}

VENDOR_ORDER_TRANSITIONS = {
    OrderStatus.PENDING.value: {OrderStatus.CONFIRMED.value, OrderStatus.CANCELLED.value},
    OrderStatus.CONFIRMED.value: {OrderStatus.PACKED.value, OrderStatus.CANCELLED.value},
    OrderStatus.PACKED.value: {OrderStatus.SHIPPED.value},
    OrderStatus.SHIPPED.value: set(),
    OrderStatus.DELIVERED.value: set(),
    OrderStatus.CANCELLED.value: set(),
    OrderStatus.RETURNED.value: set(),
}


def _resolve_vendor_profile(user):
    vp = VendorProfile.query.filter_by(user_id=user.id).first()
    if vp:
        return vp

    # Allow first-time vendor profile bootstrapping.
    vp = VendorProfile(
        user_id=user.id,
        store_name=f"{user.name} Store",
        store_slug=slugify(f"{user.name}-store-{user.id}"),
        kyc_status=VendorKycStatus.PENDING.value,
    )
    db.session.add(vp)
    db.session.flush()
    return vp


@vendor_bp.get("/products")
@role_required(Role.VENDOR)
def list_vendor_products():
    user = current_user()
    vendor = _resolve_vendor_profile(user)

    rows = Product.query.filter_by(vendor_id=vendor.id).order_by(Product.created_at.desc()).all()
    return jsonify(
        [
            {
                "id": p.id,
                "name": p.name,
                "sku": p.sku,
                "price": p.price,
                "discount_price": p.discount_price,
                "stock_quantity": p.stock_quantity,
                "status": p.status,
                "approval_status": p.approval_status,
                "category_id": p.category_id,
            }
            for p in rows
        ]
    )


@vendor_bp.post("/products")
@role_required(Role.VENDOR)
def create_product():
    user = current_user()
    vendor = _resolve_vendor_profile(user)
    if vendor.kyc_status != VendorKycStatus.APPROVED.value:
        return jsonify({"error": "Vendor KYC not approved"}), 403

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    sku = (data.get("sku") or "").strip()
    category_id = data.get("category_id")
    price = float(data.get("price", 0))

    if not name or not sku or not category_id or price <= 0:
        return jsonify({"error": "name, sku, category_id, price are required"}), 400
    if Product.query.filter_by(sku=sku).first():
        return jsonify({"error": "SKU already exists"}), 409

    category = Category.query.get(category_id)
    if not category:
        return jsonify({"error": "Category not found"}), 404

    product = Product(
        vendor_id=vendor.id,
        category_id=category_id,
        name=name,
        description=data.get("description"),
        price=price,
        discount_price=data.get("discount_price"),
        stock_quantity=max(int(data.get("stock_quantity", 0)), 0),
        sku=sku,
        status=ProductStatus.ACTIVE.value,
        approval_status=ProductApprovalStatus.PENDING.value,
        brand=data.get("brand"),
        created_by=user.id,
        updated_by=user.id,
    )
    db.session.add(product)
    db.session.commit()

    return jsonify({"id": product.id, "name": product.name, "approval_status": product.approval_status}), 201


@vendor_bp.patch("/products/<int:product_id>")
@role_required(Role.VENDOR)
def update_product(product_id: int):
    user = current_user()
    vendor = _resolve_vendor_profile(user)

    product = Product.query.filter_by(id=product_id, vendor_id=vendor.id).first()
    if not product:
        return jsonify({"error": "Product not found"}), 404

    data = request.get_json(silent=True) or {}
    for field in [
        "name",
        "description",
        "discount_price",
        "brand",
        "status",
        "availability_status",
        "thumbnail",
        "warranty_information",
        "shipping_information",
        "return_policy",
    ]:
        if field in data:
            setattr(product, field, data[field])

    if "price" in data:
        price = float(data["price"])
        if price <= 0:
            return jsonify({"error": "price must be > 0"}), 400
        product.price = price
    if "stock_quantity" in data:
        product.stock_quantity = max(int(data["stock_quantity"]), 0)

    product.updated_by = user.id
    db.session.commit()
    return jsonify({"id": product.id, "name": product.name, "status": product.status, "stock_quantity": product.stock_quantity})


@vendor_bp.get("/orders")
@role_required(Role.VENDOR)
def list_vendor_orders():
    user = current_user()
    vendor = _resolve_vendor_profile(user)

    rows = (
        db.session.query(Order, OrderItem)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .filter(OrderItem.vendor_id == vendor.id)
        .order_by(Order.created_at.desc())
        .all()
    )

    payload = []
    for order, item in rows:
        payload.append(
            {
                "order_id": order.id,
                "order_status": order.order_status,
                "payment_status": order.payment_status,
                "order_item_id": item.id,
                "product_id": item.product_id,
                "quantity": item.quantity,
                "price": item.price,
                "created_at": order.created_at.isoformat(),
            }
        )
    return jsonify(payload)


@vendor_bp.patch("/orders/<int:order_id>/status")
@role_required(Role.VENDOR)
def update_vendor_order_status(order_id: int):
    user = current_user()
    vendor = _resolve_vendor_profile(user)

    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404

    vendor_has_item = OrderItem.query.filter_by(order_id=order.id, vendor_id=vendor.id).first()
    if not vendor_has_item:
        return jsonify({"error": "Order does not belong to this vendor"}), 403

    data = request.get_json(silent=True) or {}
    new_status = (data.get("status") or "").lower()
    if new_status not in VALID_VENDOR_ORDER_STATUS:
        return jsonify({"error": "Invalid status"}), 400

    current_status = (order.order_status or "").lower()
    if current_status == new_status:
        return jsonify({"order_id": order.id, "order_status": order.order_status, "payment_status": order.payment_status})

    allowed_next = VENDOR_ORDER_TRANSITIONS.get(current_status, set())
    if new_status not in allowed_next:
        return jsonify({"error": "Vendor cannot set this status transition"}), 400

    order.order_status = new_status

    db.session.commit()
    return jsonify({"order_id": order.id, "order_status": order.order_status, "payment_status": order.payment_status})
