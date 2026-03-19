from datetime import date, datetime, timezone

from flask import Blueprint, jsonify, request

from app.common.authz import current_user, role_required
from app.extensions import db
from app.finance.service import ensure_delivery_ledger_for_shipment
from app.models import Address, DeliveryProfile, Order, OrderStatus, PaymentStatus, Role, Shipment, ShipmentStatus
from app.payments.service import mark_cod_confirmed


delivery_bp = Blueprint("delivery", __name__)

DELIVERY_BOY_STATUS = {
    ShipmentStatus.PICKED.value,
    ShipmentStatus.IN_TRANSIT.value,
    ShipmentStatus.OUT_FOR_DELIVERY.value,
    ShipmentStatus.FAILED.value,
}


def _delivery_shipment_item(s):
    order = Order.query.get(s.order_id)
    address = Address.query.get(order.shipping_address_id) if order else None
    customer_name = address.full_name if address else None
    customer_phone = address.phone if address else None
    item_count = 0
    order_total = None
    if order:
        order_total = order.total_amount
        for row in order.items.all():
            item_count += int(row.quantity or 0)
    address_text = None
    if address:
        parts = [address.address_line_1, address.address_line_2, address.city, address.state, address.postal_code]
        address_text = ", ".join(p for p in parts if p)

    return {
        "id": s.id,
        "order_id": s.order_id,
        "tracking_number": s.tracking_number,
        "shipment_status": s.shipment_status,
        "assigned_time": s.assigned_time.isoformat() if s.assigned_time else None,
        "pickup_time": s.pickup_time.isoformat() if s.pickup_time else None,
        "delivery_time": s.delivery_time.isoformat() if s.delivery_time else None,
        "delivery_attempts": s.delivery_attempts or 0,
        "failure_reason": s.failure_reason,
        "proof_of_delivery_url": s.proof_of_delivery_url,
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "customer_address": address_text,
        "item_count": item_count,
        "order_total": order_total,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@delivery_bp.get("/shipments")
@role_required(Role.DELIVERY_BOY)
def list_my_shipments():
    user = current_user()
    profile = DeliveryProfile.query.filter_by(user_id=user.id).first()
    if not profile or not profile.is_active:
        return jsonify({"error": "Delivery profile not found or inactive"}), 403

    status_filter = request.args.get("status", "").strip().lower()
    query = Shipment.query.filter(Shipment.assigned_delivery_boy_id == profile.id)
    if status_filter:
        query = query.filter(Shipment.shipment_status == status_filter)
    shipments = query.order_by(Shipment.assigned_time.desc().nullslast(), Shipment.created_at.desc()).all()
    return jsonify([_delivery_shipment_item(s) for s in shipments])


@delivery_bp.get("/shipments/<int:shipment_id>")
@role_required(Role.DELIVERY_BOY)
def get_shipment(shipment_id: int):
    user = current_user()
    profile = DeliveryProfile.query.filter_by(user_id=user.id).first()
    if not profile or not profile.is_active:
        return jsonify({"error": "Delivery profile not found or inactive"}), 403

    shipment = Shipment.query.filter_by(id=shipment_id, assigned_delivery_boy_id=profile.id).first()
    if not shipment:
        return jsonify({"error": "Shipment not found"}), 404
    return jsonify(_delivery_shipment_item(shipment))


@delivery_bp.patch("/shipments/<int:shipment_id>/status")
@role_required(Role.DELIVERY_BOY)
def update_shipment_status(shipment_id: int):
    user = current_user()
    profile = DeliveryProfile.query.filter_by(user_id=user.id).first()
    if not profile or not profile.is_active:
        return jsonify({"error": "Delivery profile not found or inactive"}), 403

    shipment = Shipment.query.filter_by(id=shipment_id, assigned_delivery_boy_id=profile.id).first()
    if not shipment:
        return jsonify({"error": "Shipment not found"}), 404

    data = request.get_json(silent=True) or {}
    new_status = (data.get("status") or "").strip().lower()
    if new_status == ShipmentStatus.DELIVERED.value:
        return jsonify({"error": "Use POST /confirm to confirm delivery with OTP"}), 400
    if new_status not in DELIVERY_BOY_STATUS:
        return jsonify({"error": "Invalid status. Allowed: picked, in_transit, out_for_delivery, failed"}), 400

    shipment.shipment_status = new_status
    if new_status == ShipmentStatus.PICKED.value:
        shipment.pickup_time = shipment.pickup_time or datetime.now(timezone.utc)
    if new_status == ShipmentStatus.FAILED.value:
        shipment.failure_reason = (data.get("failure_reason") or "").strip() or None
        shipment.delivery_attempts = (shipment.delivery_attempts or 0) + 1

    order = Order.query.get(shipment.order_id)
    if order and new_status in {
        ShipmentStatus.PICKED.value,
        ShipmentStatus.IN_TRANSIT.value,
        ShipmentStatus.OUT_FOR_DELIVERY.value,
    }:
        order.order_status = OrderStatus.SHIPPED.value

    if data.get("proof_of_delivery_url"):
        shipment.proof_of_delivery_url = data["proof_of_delivery_url"]

    db.session.commit()
    return jsonify(_delivery_shipment_item(shipment))


@delivery_bp.post("/shipments/<int:shipment_id>/confirm")
@role_required(Role.DELIVERY_BOY)
def confirm_delivery(shipment_id: int):
    user = current_user()
    profile = DeliveryProfile.query.filter_by(user_id=user.id).first()
    if not profile or not profile.is_active:
        return jsonify({"error": "Delivery profile not found or inactive"}), 403

    shipment = Shipment.query.filter_by(id=shipment_id, assigned_delivery_boy_id=profile.id).first()
    if not shipment:
        return jsonify({"error": "Shipment not found"}), 404

    data = request.get_json(silent=True) or {}
    if shipment.shipment_status == ShipmentStatus.DELIVERED.value:
        return jsonify({"error": "Shipment is already delivered"}), 400
    if shipment.shipment_status != ShipmentStatus.OUT_FOR_DELIVERY.value:
        return jsonify({"error": "Shipment must be out_for_delivery before OTP confirmation"}), 400

    otp = (data.get("otp") or "").strip()
    if not otp:
        return jsonify({"error": "otp is required"}), 400
    if shipment.otp_code and otp != shipment.otp_code:
        shipment.delivery_attempts = (shipment.delivery_attempts or 0) + 1
        db.session.commit()
        return jsonify({"error": "Invalid delivery OTP"}), 400

    shipment.shipment_status = ShipmentStatus.DELIVERED.value
    shipment.delivery_time = datetime.now(timezone.utc)
    shipment.failure_reason = None
    if data.get("proof_of_delivery_url"):
        shipment.proof_of_delivery_url = data["proof_of_delivery_url"]

    order = Order.query.get(shipment.order_id)
    if order:
        order.order_status = OrderStatus.DELIVERED.value
        if order.payment_status == PaymentStatus.COD_PENDING.value:
            order.payment_status = PaymentStatus.COD_CONFIRMED.value
            mark_cod_confirmed(order.id)

    ensure_delivery_ledger_for_shipment(shipment.id)

    db.session.commit()
    return jsonify(_delivery_shipment_item(shipment))


@delivery_bp.get("/dashboard")
@role_required(Role.DELIVERY_BOY)
def dashboard():
    user = current_user()
    profile = DeliveryProfile.query.filter_by(user_id=user.id).first()
    if not profile or not profile.is_active:
        return jsonify({"error": "Delivery profile not found or inactive"}), 403

    base = Shipment.query.filter(Shipment.assigned_delivery_boy_id == profile.id)
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)

    today_deliveries = base.filter(Shipment.assigned_time >= today_start).count()
    completed = base.filter(Shipment.shipment_status == ShipmentStatus.DELIVERED.value).count()
    failed = base.filter(Shipment.shipment_status == ShipmentStatus.FAILED.value).count()
    pending = base.filter(
        Shipment.shipment_status.in_([
            ShipmentStatus.PICKUP_REQUESTED.value,
            ShipmentStatus.PICKED.value,
            ShipmentStatus.IN_TRANSIT.value,
            ShipmentStatus.OUT_FOR_DELIVERY.value,
        ])
    ).count()

    return jsonify({
        "today_deliveries": today_deliveries,
        "completed_deliveries": completed,
        "failed_deliveries": failed,
        "pending_deliveries": pending,
    })
