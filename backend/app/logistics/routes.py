from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.common.authz import current_user, role_required
from app.extensions import db
from app.models import (
    Address,
    DeliveryProfile,
    LogisticsProfile,
    Order,
    OrderStatus,
    Role,
    Shipment,
    ShipmentStatus,
    User,
)


logistics_bp = Blueprint("logistics", __name__)

VALID_SHIPMENT_STATUS = {
    ShipmentStatus.PICKUP_REQUESTED.value,
    ShipmentStatus.PICKED.value,
    ShipmentStatus.IN_TRANSIT.value,
    ShipmentStatus.OUT_FOR_DELIVERY.value,
    ShipmentStatus.FAILED.value,
}


def _shipment_item(s):
    order = Order.query.get(s.order_id)
    address = Address.query.get(order.shipping_address_id) if order else None
    customer_name = address.full_name if address else None
    customer_phone = address.phone if address else None
    customer_address = None
    if address:
        address_parts = [
            address.address_line_1,
            address.address_line_2,
            address.city,
            address.state,
            address.postal_code,
        ]
        customer_address = ", ".join(part for part in address_parts if part)

    out = {
        "id": s.id,
        "order_id": s.order_id,
        "logistics_id": s.logistics_id,
        "assigned_delivery_boy_id": s.assigned_delivery_boy_id,
        "assigned_by_logistics_id": s.assigned_by_logistics_id,
        "assigned_time": s.assigned_time.isoformat() if s.assigned_time else None,
        "pickup_time": s.pickup_time.isoformat() if s.pickup_time else None,
        "delivery_time": s.delivery_time.isoformat() if s.delivery_time else None,
        "tracking_number": s.tracking_number,
        "shipment_status": s.shipment_status,
        "delivery_attempts": s.delivery_attempts or 0,
        "proof_of_delivery_url": s.proof_of_delivery_url,
        "failure_reason": s.failure_reason,
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "customer_address": customer_address,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }
    if s.assigned_delivery_boy and s.assigned_delivery_boy.user:
        out["assigned_delivery_boy_name"] = s.assigned_delivery_boy.user.name
    return out


@logistics_bp.get("/dashboard")
@role_required(Role.LOGISTICS, Role.ADMIN)
def dashboard():
    query = Shipment.query
    total = query.count()
    unassigned = query.filter(Shipment.assigned_delivery_boy_id.is_(None)).count()
    assigned = query.filter(Shipment.assigned_delivery_boy_id.isnot(None)).count()
    delivered = query.filter(Shipment.shipment_status == ShipmentStatus.DELIVERED.value).count()
    failed = query.filter(Shipment.shipment_status == ShipmentStatus.FAILED.value).count()
    return jsonify({
        "total_shipments": total,
        "unassigned_shipments": unassigned,
        "assigned_shipments": assigned,
        "delivered_shipments": delivered,
        "failed_deliveries": failed,
    })


@logistics_bp.get("/shipments")
@role_required(Role.LOGISTICS, Role.ADMIN)
def list_shipments():
    user = current_user()
    query = Shipment.query
    if user.role == Role.LOGISTICS.value:
        profile = LogisticsProfile.query.filter_by(user_id=user.id).first()
        if not profile:
            return jsonify({"error": "Logistics profile not found"}), 404
        query = query.filter((Shipment.logistics_id == profile.id) | (Shipment.logistics_id.is_(None)))

    status_filter = request.args.get("status", "").strip().lower()
    if status_filter:
        query = query.filter(Shipment.shipment_status == status_filter)

    shipments = query.order_by(Shipment.created_at.desc()).all()
    return jsonify([_shipment_item(s) for s in shipments])


@logistics_bp.patch("/shipments/<int:shipment_id>/assign")
@role_required(Role.LOGISTICS, Role.ADMIN)
def assign_delivery_boy(shipment_id: int):
    user = current_user()
    shipment = Shipment.query.get(shipment_id)
    if not shipment:
        return jsonify({"error": "Shipment not found"}), 404
    if user.role == Role.LOGISTICS.value:
        profile = LogisticsProfile.query.filter_by(user_id=user.id).first()
        if not profile:
            return jsonify({"error": "Logistics profile not found"}), 404
        shipment.logistics_id = profile.id

    data = request.get_json(silent=True) or {}
    delivery_boy_id = data.get("delivery_boy_id")
    if delivery_boy_id is None:
        return jsonify({"error": "delivery_boy_id is required"}), 400
    profile = DeliveryProfile.query.get(delivery_boy_id)
    if not profile or not profile.is_active:
        return jsonify({"error": "Delivery boy not found or inactive"}), 400

    shipment.assigned_delivery_boy_id = profile.id
    shipment.assigned_by_logistics_id = user.id
    shipment.assigned_time = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(_shipment_item(shipment))


@logistics_bp.get("/delivery-boys")
@role_required(Role.LOGISTICS, Role.ADMIN)
def list_delivery_boys():
    profiles = (
        DeliveryProfile.query.join(User)
        .filter(User.deleted_at.is_(None))
        .order_by(User.name)
        .all()
    )
    return jsonify(
        [
            {
                "id": p.id,
                "user_id": p.user_id,
                "name": p.user.name,
                "email": p.user.email,
                "phone": p.phone or p.user.phone,
                "vehicle_type": p.vehicle_type,
                "is_active": p.is_active,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in profiles
        ]
    )


@logistics_bp.patch("/delivery-boys/<int:profile_id>")
@role_required(Role.LOGISTICS, Role.ADMIN)
def update_delivery_boy_status(profile_id: int):
    profile = DeliveryProfile.query.get(profile_id)
    if not profile:
        return jsonify({"error": "Delivery boy not found"}), 404
    data = request.get_json(silent=True) or {}
    if "is_active" in data:
        profile.is_active = bool(data["is_active"])
    db.session.commit()
    return jsonify({
        "id": profile.id,
        "user_id": profile.user_id,
        "is_active": profile.is_active,
    })


@logistics_bp.patch("/shipments/<int:shipment_id>/status")
@role_required(Role.LOGISTICS, Role.ADMIN)
def update_shipment_status(shipment_id: int):
    user = current_user()
    shipment = Shipment.query.get(shipment_id)
    if not shipment:
        return jsonify({"error": "Shipment not found"}), 404

    profile = None
    if user.role == Role.LOGISTICS.value:
        profile = LogisticsProfile.query.filter_by(user_id=user.id).first()
        if not profile:
            return jsonify({"error": "Logistics profile not found"}), 404
        if shipment.logistics_id and shipment.logistics_id != profile.id:
            return jsonify({"error": "Shipment assigned to a different logistics user"}), 403
        if shipment.logistics_id is None:
            shipment.logistics_id = profile.id

    data = request.get_json(silent=True) or {}
    new_status = (data.get("status") or "").lower()
    if new_status == ShipmentStatus.DELIVERED.value:
        return jsonify({"error": "Final delivery must be confirmed by delivery boy with OTP"}), 400
    if new_status not in VALID_SHIPMENT_STATUS:
        return jsonify({"error": "Invalid status"}), 400

    shipment.shipment_status = new_status
    if data.get("proof_of_delivery_url"):
        shipment.proof_of_delivery_url = data["proof_of_delivery_url"]
    if new_status == ShipmentStatus.PICKED.value:
        shipment.pickup_time = shipment.pickup_time or datetime.now(timezone.utc)
    if new_status == ShipmentStatus.FAILED.value:
        shipment.failure_reason = (data.get("failure_reason") or "").strip() or None
        shipment.delivery_attempts = (shipment.delivery_attempts or 0) + 1

    order = Order.query.get(shipment.order_id)
    if order:
        if new_status in {
            ShipmentStatus.PICKED.value,
            ShipmentStatus.IN_TRANSIT.value,
            ShipmentStatus.OUT_FOR_DELIVERY.value,
        }:
            order.order_status = OrderStatus.SHIPPED.value

    db.session.commit()
    return jsonify(_shipment_item(shipment))
