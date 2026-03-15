import re

from flask import Blueprint, jsonify, request
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.common.authz import current_user, role_required
from app.extensions import db
from app.models import Address, CartItem, CustomerPaymentCard, Product, Role, WishlistItem


cart_bp = Blueprint("cart", __name__)
PIN_PATTERN = re.compile(r"^\d{4}$")


def _digits_only(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _ensure_payment_card_table() -> None:
    inspector = inspect(db.engine)
    if not inspector.has_table(CustomerPaymentCard.__tablename__):
        CustomerPaymentCard.__table__.create(bind=db.engine, checkfirst=True)


@cart_bp.get("/cart/items")
@role_required(Role.CUSTOMER)
def list_cart_items():
    user = current_user()
    items = CartItem.query.filter_by(customer_id=user.id).order_by(CartItem.created_at.desc()).all()

    payload = []
    for item in items:
        product = Product.query.get(item.product_id)
        if not product:
            continue
        payload.append(
            {
                "id": item.id,
                "product_id": item.product_id,
                "quantity": item.quantity,
                "product": {
                    "name": product.name,
                    "price": product.price,
                    "discount_price": product.discount_price,
                    "stock_quantity": product.stock_quantity,
                },
            }
        )
    return jsonify(payload)


@cart_bp.post("/cart/items")
@role_required(Role.CUSTOMER)
def add_cart_item():
    user = current_user()
    data = request.get_json(silent=True) or {}
    product_id = data.get("product_id")
    quantity = max(int(data.get("quantity", 1)), 1)

    product = Product.query.get(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404
    if product.stock_quantity < quantity:
        return jsonify({"error": "Insufficient stock"}), 400

    item = CartItem.query.filter_by(customer_id=user.id, product_id=product_id).first()
    if item:
        item.quantity = quantity
    else:
        item = CartItem(customer_id=user.id, product_id=product_id, quantity=quantity)
        db.session.add(item)

    db.session.commit()
    return jsonify({"id": item.id, "product_id": item.product_id, "quantity": item.quantity}), 201


@cart_bp.patch("/cart/items/<int:item_id>")
@role_required(Role.CUSTOMER)
def update_cart_item(item_id: int):
    user = current_user()
    data = request.get_json(silent=True) or {}
    quantity = max(int(data.get("quantity", 1)), 1)

    item = CartItem.query.filter_by(id=item_id, customer_id=user.id).first()
    if not item:
        return jsonify({"error": "Cart item not found"}), 404

    product = Product.query.get(item.product_id)
    if not product or product.stock_quantity < quantity:
        return jsonify({"error": "Insufficient stock"}), 400

    item.quantity = quantity
    db.session.commit()
    return jsonify({"id": item.id, "quantity": item.quantity})


@cart_bp.delete("/cart/items/<int:item_id>")
@role_required(Role.CUSTOMER)
def delete_cart_item(item_id: int):
    user = current_user()
    item = CartItem.query.filter_by(id=item_id, customer_id=user.id).first()
    if not item:
        return jsonify({"error": "Cart item not found"}), 404

    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Cart item deleted"})


@cart_bp.get("/wishlist/items")
@role_required(Role.CUSTOMER)
def list_wishlist_items():
    user = current_user()
    items = WishlistItem.query.filter_by(customer_id=user.id).order_by(WishlistItem.created_at.desc()).all()
    return jsonify([{"id": item.id, "product_id": item.product_id} for item in items])


@cart_bp.post("/wishlist/items")
@role_required(Role.CUSTOMER)
def add_wishlist_item():
    user = current_user()
    data = request.get_json(silent=True) or {}
    product_id = data.get("product_id")

    if not Product.query.get(product_id):
        return jsonify({"error": "Product not found"}), 404

    existing = WishlistItem.query.filter_by(customer_id=user.id, product_id=product_id).first()
    if existing:
        return jsonify({"id": existing.id, "product_id": existing.product_id})

    row = WishlistItem(customer_id=user.id, product_id=product_id)
    db.session.add(row)
    db.session.commit()
    return jsonify({"id": row.id, "product_id": row.product_id}), 201


@cart_bp.delete("/wishlist/items/<int:item_id>")
@role_required(Role.CUSTOMER)
def delete_wishlist_item(item_id: int):
    user = current_user()
    item = WishlistItem.query.filter_by(id=item_id, customer_id=user.id).first()
    if not item:
        return jsonify({"error": "Wishlist item not found"}), 404

    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Wishlist item deleted"})


@cart_bp.get("/addresses")
@role_required(Role.CUSTOMER)
def list_addresses():
    user = current_user()
    rows = Address.query.filter_by(user_id=user.id).order_by(Address.is_default.desc(), Address.created_at.desc()).all()
    return jsonify(
        [
            {
                "id": row.id,
                "full_name": row.full_name,
                "phone": row.phone,
                "address_line_1": row.address_line_1,
                "address_line_2": row.address_line_2,
                "city": row.city,
                "state": row.state,
                "postal_code": row.postal_code,
                "country": row.country,
                "is_default": row.is_default,
            }
            for row in rows
        ]
    )


@cart_bp.post("/addresses")
@role_required(Role.CUSTOMER)
def create_address():
    user = current_user()
    data = request.get_json(silent=True) or {}

    required = ["full_name", "phone", "address_line_1", "city", "state", "postal_code"]
    if any(not (data.get(field) or "").strip() for field in required):
        return jsonify({"error": "full_name, phone, address_line_1, city, state, postal_code are required"}), 400

    is_default = bool(data.get("is_default", False))
    if is_default:
        Address.query.filter_by(user_id=user.id, is_default=True).update({"is_default": False})

    address = Address(
        user_id=user.id,
        full_name=data["full_name"].strip(),
        phone=data["phone"].strip(),
        address_line_1=data["address_line_1"].strip(),
        address_line_2=(data.get("address_line_2") or "").strip() or None,
        city=data["city"].strip(),
        state=data["state"].strip(),
        postal_code=data["postal_code"].strip(),
        country=(data.get("country") or "India").strip(),
        is_default=is_default,
    )
    db.session.add(address)
    db.session.commit()

    return (
        jsonify(
            {
                "id": address.id,
                "full_name": address.full_name,
                "phone": address.phone,
                "address_line_1": address.address_line_1,
                "address_line_2": address.address_line_2,
                "city": address.city,
                "state": address.state,
                "postal_code": address.postal_code,
                "country": address.country,
                "is_default": address.is_default,
            }
        ),
        201,
    )


@cart_bp.get("/payment-card")
@role_required(Role.CUSTOMER)
def get_saved_payment_card():
    user = current_user()
    _ensure_payment_card_table()
    card = CustomerPaymentCard.query.filter_by(customer_id=user.id).first()
    if not card:
        return jsonify({"has_card": False, "cardholder_name": None, "card_last4": None, "updated_at": None})

    return jsonify(
        {
            "has_card": True,
            "cardholder_name": card.cardholder_name,
            "card_last4": card.card_last4,
            "updated_at": card.updated_at.isoformat() if card.updated_at else None,
        }
    )


@cart_bp.put("/payment-card")
@role_required(Role.CUSTOMER)
def save_payment_card():
    user = current_user()
    _ensure_payment_card_table()
    data = request.get_json(silent=True) or {}

    cardholder_name = (data.get("cardholder_name") or "").strip()
    card_number = _digits_only(data.get("card_number") or "")
    card_pin = (data.get("card_pin") or "").strip()

    if not cardholder_name:
        return jsonify({"error": "cardholder_name is required"}), 400
    if len(card_number) < 12 or len(card_number) > 19:
        return jsonify({"error": "card_number must be 12 to 19 digits"}), 400
    if not PIN_PATTERN.match(card_pin):
        return jsonify({"error": "card_pin must be exactly 4 digits"}), 400

    try:
        card = CustomerPaymentCard.query.filter_by(customer_id=user.id).first()
        if not card:
            card = CustomerPaymentCard(customer_id=user.id)
            db.session.add(card)

        card.cardholder_name = cardholder_name[:120]
        card.card_last4 = card_number[-4:]
        card.set_card_number(card_number)
        card.set_card_pin(card_pin)

        db.session.commit()
        return jsonify(
            {
                "has_card": True,
                "cardholder_name": card.cardholder_name,
                "card_last4": card.card_last4,
                "updated_at": card.updated_at.isoformat() if card.updated_at else None,
            }
        )
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "Unable to save card right now. Please retry after restarting backend."}), 500
