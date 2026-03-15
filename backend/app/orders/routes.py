import random
import string

from flask import Blueprint, jsonify, request

from app.common.authz import current_user, role_required
from app.extensions import db, limiter
from app.models import (
    Address,
    CartItem,
    Commission,
    LogisticsProfile,
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    Payment,
    PaymentStatus,
    Product,
    Role,
    Shipment,
    ShipmentStatus,
)
from app.payments.service import create_card_payment, create_cod_payment, verify_customer_card


orders_bp = Blueprint("orders", __name__)
DEFAULT_COMMISSION_PERCENTAGE = 10.0


def _order_payload(order: Order):
    items = []
    for item in order.items.order_by(OrderItem.id.asc()).all():
        product = Product.query.get(item.product_id)
        items.append(
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": product.name if product else None,
                "vendor_id": item.vendor_id,
                "quantity": item.quantity,
                "price": item.price,
                "subtotal": round(item.quantity * item.price, 2),
            }
        )

    payments = []
    for payment in Payment.query.filter_by(order_id=order.id).order_by(Payment.id.asc()).all():
        payments.append(
            {
                "id": payment.id,
                "payment_method": payment.payment_method,
                "payment_status": payment.payment_status,
                "transaction_id": payment.transaction_id,
                "amount": payment.amount,
                "created_at": payment.created_at.isoformat() if payment.created_at else None,
            }
        )

    shipment = Shipment.query.filter_by(order_id=order.id).order_by(Shipment.id.desc()).first()
    shipping_address = Address.query.get(order.shipping_address_id)

    def _shipment_payload(s):
        p = {
            "id": s.id,
            "logistics_id": s.logistics_id,
            "assigned_delivery_boy_id": s.assigned_delivery_boy_id,
            "assigned_by_logistics_id": s.assigned_by_logistics_id,
            "assigned_time": s.assigned_time.isoformat() if s.assigned_time else None,
            "pickup_time": s.pickup_time.isoformat() if s.pickup_time else None,
            "delivery_time": s.delivery_time.isoformat() if s.delivery_time else None,
            "tracking_number": s.tracking_number,
            "shipment_status": s.shipment_status,
            "otp_code": s.otp_code,
            "delivery_attempts": s.delivery_attempts or 0,
            "proof_of_delivery_url": s.proof_of_delivery_url,
            "failure_reason": s.failure_reason,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        if getattr(s, "assigned_delivery_boy", None) and s.assigned_delivery_boy.user:
            p["assigned_delivery_boy_name"] = s.assigned_delivery_boy.user.name
        return p

    return {
        "id": order.id,
        "customer_id": order.customer_id,
        "total_amount": order.total_amount,
        "payment_status": order.payment_status,
        "order_status": order.order_status,
        "shipping_address_id": order.shipping_address_id,
        "created_at": order.created_at.isoformat(),
        "items": items,
        "payments": payments,
        "shipment": _shipment_payload(shipment) if shipment else None,
        "shipping_address": (
            {
                "id": shipping_address.id,
                "full_name": shipping_address.full_name,
                "phone": shipping_address.phone,
                "address_line_1": shipping_address.address_line_1,
                "address_line_2": shipping_address.address_line_2,
                "city": shipping_address.city,
                "state": shipping_address.state,
                "postal_code": shipping_address.postal_code,
                "country": shipping_address.country,
            }
            if shipping_address
            else None
        ),
    }


@orders_bp.post("/orders")
@role_required(Role.CUSTOMER)
@limiter.limit("20 per hour")
def create_order():
    user = current_user()
    data = request.get_json(silent=True) or {}
    shipping_address_id = data.get("shipping_address_id")
    payment_method = str(data.get("payment_method", PaymentMethod.COD.value)).strip().lower()
    card_number = "".join(ch for ch in str(data.get("card_number") or "") if ch.isdigit())
    card_pin = str(data.get("card_pin") or "").strip()
    try:
        shipping_fee = max(float(data.get("shipping_fee", 0) or 0), 0.0)
        tax_amount = max(float(data.get("tax_amount", 0) or 0), 0.0)
    except (TypeError, ValueError):
        return jsonify({"error": "shipping_fee and tax_amount must be numbers"}), 400

    if not shipping_address_id:
        return jsonify({"error": "shipping_address_id is required"}), 400
    if payment_method not in {PaymentMethod.COD.value, PaymentMethod.CARD.value}:
        return jsonify({"error": "payment_method must be cod or card"}), 400

    address = Address.query.filter_by(id=shipping_address_id, user_id=user.id).first()
    if not address:
        return jsonify({"error": "Invalid shipping address"}), 400

    matched_card = None
    if payment_method == PaymentMethod.CARD.value:
        if not card_number or not card_pin:
            return jsonify({"error": "card_number and card_pin are required for card payment"}), 400
        matched_card = verify_customer_card(user.id, card_number, card_pin)
        if not matched_card:
            return jsonify({"error": "Card number or PIN did not match saved profile card"}), 400

    use_cart = data.get("use_cart", True)
    order_rows = []

    if use_cart:
        cart_items = CartItem.query.filter_by(customer_id=user.id).all()
        if not cart_items:
            return jsonify({"error": "Cart is empty"}), 400

        for row in cart_items:
            product = Product.query.get(row.product_id)
            if not product:
                return jsonify({"error": f"Product {row.product_id} not found"}), 404
            if row.quantity > product.stock_quantity:
                return jsonify({"error": f"Insufficient stock for product {product.id}"}), 400
            order_rows.append((product, row.quantity))
    else:
        items = data.get("items") or []
        if not items:
            return jsonify({"error": "items are required when use_cart=false"}), 400
        for item in items:
            product = Product.query.get(item.get("product_id"))
            quantity = max(int(item.get("quantity", 1)), 1)
            if not product:
                return jsonify({"error": f"Product {item.get('product_id')} not found"}), 404
            if quantity > product.stock_quantity:
                return jsonify({"error": f"Insufficient stock for product {product.id}"}), 400
            order_rows.append((product, quantity))

    item_total = 0.0
    for product, quantity in order_rows:
        effective_price = product.discount_price if product.discount_price else product.price
        item_total += effective_price * quantity
    total_amount = round(item_total + shipping_fee + tax_amount, 2)

    order = Order(
        customer_id=user.id,
        total_amount=total_amount,
        payment_status=(
            PaymentStatus.COD_PENDING.value if payment_method == PaymentMethod.COD.value else PaymentStatus.PAID.value
        ),
        order_status=OrderStatus.PENDING.value,
        shipping_address_id=shipping_address_id,
    )
    db.session.add(order)
    db.session.flush()

    for product, quantity in order_rows:
        price = product.discount_price if product.discount_price else product.price
        oi = OrderItem(order_id=order.id, product_id=product.id, vendor_id=product.vendor_id, quantity=quantity, price=price)
        db.session.add(oi)
        db.session.flush()

        product.stock_quantity -= quantity

        commission_amount = round((price * quantity) * (DEFAULT_COMMISSION_PERCENTAGE / 100.0), 2)
        vendor_amount = round(price * quantity - commission_amount, 2)
        db.session.add(
            Commission(
                order_item_id=oi.id,
                vendor_amount=vendor_amount,
                platform_commission=commission_amount,
                commission_percentage=DEFAULT_COMMISSION_PERCENTAGE,
            )
        )

    if payment_method == PaymentMethod.COD.value:
        create_cod_payment(order_id=order.id, amount=order.total_amount)
    else:
        create_card_payment(order_id=order.id, amount=order.total_amount, card_last4=matched_card.card_last4)

    tracking = f"TRK{order.id:06d}"
    otp = "".join(random.choices(string.digits, k=6))
    shipment = Shipment(
        order_id=order.id,
        logistics_id=None,
        tracking_number=tracking,
        shipment_status=ShipmentStatus.PICKUP_REQUESTED.value,
        otp_code=otp,
    )
    db.session.add(shipment)

    if use_cart:
        CartItem.query.filter_by(customer_id=user.id).delete()

    db.session.commit()
    return jsonify(_order_payload(order)), 201


@orders_bp.get("/orders")
@role_required(Role.CUSTOMER)
def list_orders():
    user = current_user()
    orders = Order.query.filter_by(customer_id=user.id).order_by(Order.created_at.desc()).all()
    return jsonify([_order_payload(order) for order in orders])


@orders_bp.get("/orders/<int:order_id>")
@role_required(Role.CUSTOMER)
def get_order(order_id: int):
    user = current_user()
    order = Order.query.filter_by(id=order_id, customer_id=user.id).first()
    if not order:
        return jsonify({"error": "Order not found"}), 404
    return jsonify(_order_payload(order))


@orders_bp.post("/orders/<int:order_id>/cancel")
@role_required(Role.CUSTOMER)
def cancel_order(order_id: int):
    user = current_user()
    order = Order.query.filter_by(id=order_id, customer_id=user.id).first()
    if not order:
        return jsonify({"error": "Order not found"}), 404

    if order.order_status not in {OrderStatus.PENDING.value, OrderStatus.CONFIRMED.value}:
        return jsonify({"error": "Order cannot be cancelled at this stage"}), 400

    order.order_status = OrderStatus.CANCELLED.value

    for item in order.items.all():
        product = Product.query.get(item.product_id)
        if product:
            product.stock_quantity += item.quantity

    db.session.commit()
    return jsonify(_order_payload(order))
