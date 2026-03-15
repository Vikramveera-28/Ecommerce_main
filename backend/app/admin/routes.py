from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from app.common.authz import role_required
from app.extensions import db
from app.models import (
    Address,
    AccountStatus,
    Category,
    DeliveryProfile,
    LogisticsProfile,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentStatus,
    Product,
    ProductApprovalStatus,
    ProductStatus,
    Role,
    Shipment,
    User,
    VendorKycStatus,
    VendorProfile,
)


admin_bp = Blueprint("admin", __name__)

RANGE_TO_DAYS = {
    "1d": 1,
    "7d": 7,
    "14d": 14,
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "12m": 365,
}


def _resolve_period():
    range_key = (request.args.get("range") or "1m").strip().lower()
    now = datetime.utcnow()

    if range_key == "custom":
        from_date = (request.args.get("from_date") or "").strip()
        to_date = (request.args.get("to_date") or "").strip()
        if not from_date or not to_date:
            return None, "from_date and to_date are required for custom range"
        try:
            start = datetime.strptime(from_date, "%Y-%m-%d")
            end = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            return None, "custom date format must be YYYY-MM-DD"
    else:
        days = RANGE_TO_DAYS.get(range_key)
        if not days:
            return None, "range must be one of 1d, 7d, 14d, 1m, 3m, 6m, 12m, custom"
        start = now - timedelta(days=days)
        end = now

    if start >= end:
        return None, "Invalid period. Start must be before end."

    return {"range": range_key, "start": start, "end": end}, None


def _to_float(value):
    return float(round(float(value or 0), 2))


def _build_revenue_trend(valid_orders, valid_order_ids, items_by_order, shipments, start, end):
    total_seconds = max((end - start).total_seconds(), 1)
    if total_seconds <= 14 * 24 * 60 * 60:
        bucket_count = max(int(total_seconds // (24 * 60 * 60)) + 1, 1)
    elif total_seconds <= 60 * 24 * 60 * 60:
        bucket_count = 8
    else:
        bucket_count = 12

    bucket_span = total_seconds / bucket_count
    buckets = []
    for index in range(bucket_count):
        bucket_start = start + timedelta(seconds=bucket_span * index)
        bucket_end = start + timedelta(seconds=bucket_span * (index + 1))
        buckets.append(
            {
                "index": index,
                "start": bucket_start,
                "end": bucket_end,
                "label": bucket_start.strftime("%d %b"),
                "revenue": 0.0,
                "items": 0,
                "deliveries": 0,
            }
        )

    def _bucket_index(ts):
        if ts is None:
            return None
        if getattr(ts, "tzinfo", None) is not None:
            ts = ts.replace(tzinfo=None)
        seconds = (ts - start).total_seconds()
        if seconds < 0 or seconds >= total_seconds:
            return None
        return min(bucket_count - 1, max(0, int(seconds / bucket_span)))

    for order in valid_orders:
        idx = _bucket_index(order.created_at)
        if idx is None:
            continue
        buckets[idx]["revenue"] += float(order.total_amount or 0)
        for item in items_by_order.get(order.id, []):
            buckets[idx]["items"] += int(item.quantity or 0)

    for shipment in shipments:
        if shipment.order_id not in valid_order_ids:
            continue
        if shipment.shipment_status != "delivered":
            continue
        event_time = shipment.delivery_time or shipment.created_at
        idx = _bucket_index(event_time)
        if idx is None:
            continue
        buckets[idx]["deliveries"] += 1

    return [
        {
            "label": bucket["label"],
            "revenue": _to_float(bucket["revenue"]),
            "items": int(bucket["items"]),
            "deliveries": int(bucket["deliveries"]),
        }
        for bucket in buckets
    ]


@admin_bp.get("/users")
@role_required(Role.ADMIN)
def list_users():
    role = request.args.get("role")
    status = request.args.get("status")

    query = User.query.filter(User.deleted_at.is_(None))
    if role:
        query = query.filter(User.role == role)
    if status:
        query = query.filter(User.status == status)

    users = query.order_by(User.created_at.desc()).all()
    return jsonify(
        [
            {
                "id": u.id,
                "name": u.name,
                "email": u.email,
                "phone": u.phone,
                "role": u.role,
                "status": u.status,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ]
    )


@admin_bp.patch("/users/<int:user_id>/status")
@role_required(Role.ADMIN)
def set_user_status(user_id: int):
    data = request.get_json(silent=True) or {}
    new_status = (data.get("status") or "").lower()
    if new_status not in {s.value for s in AccountStatus}:
        return jsonify({"error": "Invalid account status"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    user.status = new_status
    db.session.commit()
    return jsonify({"id": user.id, "status": user.status})


@admin_bp.patch("/vendors/<int:vendor_id>/approve")
@role_required(Role.ADMIN)
def approve_vendor(vendor_id: int):
    vendor = VendorProfile.query.get(vendor_id)
    if not vendor:
        return jsonify({"error": "Vendor not found"}), 404

    vendor.kyc_status = VendorKycStatus.APPROVED.value
    user = User.query.get(vendor.user_id)
    if user:
        user.status = AccountStatus.ACTIVE.value
        user.role = Role.VENDOR.value

    db.session.commit()
    return jsonify({"vendor_id": vendor.id, "kyc_status": vendor.kyc_status, "user_status": user.status if user else None})


@admin_bp.patch("/products/<int:product_id>/approve")
@role_required(Role.ADMIN)
def approve_product(product_id: int):
    product = Product.query.get(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    data = request.get_json(silent=True) or {}
    approved = bool(data.get("approved", True))
    product.approval_status = ProductApprovalStatus.APPROVED.value if approved else ProductApprovalStatus.REJECTED.value
    product.status = ProductStatus.ACTIVE.value if approved else ProductStatus.INACTIVE.value

    db.session.commit()
    return jsonify({"id": product.id, "approval_status": product.approval_status, "status": product.status})


@admin_bp.get("/reports/sales")
@role_required(Role.ADMIN)
def sales_report():
    total_orders = db.session.query(func.count(Order.id)).scalar() or 0
    total_revenue = db.session.query(func.coalesce(func.sum(Order.total_amount), 0.0)).scalar() or 0.0
    cod_pending = db.session.query(func.count(Payment.id)).filter(Payment.payment_status == PaymentStatus.COD_PENDING.value).scalar() or 0
    cod_confirmed = (
        db.session.query(func.count(Payment.id)).filter(Payment.payment_status == PaymentStatus.COD_CONFIRMED.value).scalar() or 0
    )

    by_status_rows = db.session.query(Order.order_status, func.count(Order.id)).group_by(Order.order_status).all()
    by_status = {status: count for status, count in by_status_rows}

    top_vendors_rows = (
        db.session.query(
            VendorProfile.id,
            VendorProfile.store_name,
            func.coalesce(func.sum(OrderItem.price * OrderItem.quantity), 0.0).label("gross_sales"),
        )
        .join(OrderItem, OrderItem.vendor_id == VendorProfile.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.order_status != OrderStatus.CANCELLED.value)
        .group_by(VendorProfile.id, VendorProfile.store_name)
        .order_by(func.sum(OrderItem.price * OrderItem.quantity).desc())
        .limit(10)
        .all()
    )

    return jsonify(
        {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "totals": {
                "orders": int(total_orders),
                "revenue": float(round(total_revenue, 2)),
                "cod_pending_orders": int(cod_pending),
                "cod_confirmed_orders": int(cod_confirmed),
            },
            "orders_by_status": by_status,
            "top_vendors": [
                {"vendor_id": row.id, "store_name": row.store_name, "gross_sales": float(round(row.gross_sales, 2))}
                for row in top_vendors_rows
            ],
        }
    )


@admin_bp.get("/reports/operations")
@role_required(Role.ADMIN)
def operations_report():
    period, period_error = _resolve_period()
    if period_error:
        return jsonify({"error": period_error}), 400

    start = period["start"]
    end = period["end"]
    search_q = (request.args.get("q") or "").strip().lower()

    ranged_orders = (
        Order.query.filter(Order.created_at >= start, Order.created_at < end).order_by(Order.created_at.desc()).all()
    )
    valid_orders = [order for order in ranged_orders if order.order_status != OrderStatus.CANCELLED.value]
    valid_order_ids = {order.id for order in valid_orders}

    ranged_shipments = (
        Shipment.query.filter(Shipment.created_at >= start, Shipment.created_at < end).order_by(Shipment.created_at.desc()).all()
    )
    shipment_order_ids = {shipment.order_id for shipment in ranged_shipments}
    all_relevant_order_ids = valid_order_ids | shipment_order_ids

    if all_relevant_order_ids:
        order_items = OrderItem.query.filter(OrderItem.order_id.in_(all_relevant_order_ids)).all()
        payments = Payment.query.filter(Payment.order_id.in_(all_relevant_order_ids)).all()
    else:
        order_items = []
        payments = []

    orders_by_id = {order.id: order for order in ranged_orders}
    missing_order_ids = all_relevant_order_ids - set(orders_by_id.keys())
    if missing_order_ids:
        for order in Order.query.filter(Order.id.in_(missing_order_ids)).all():
            orders_by_id[order.id] = order

    items_by_order = {}
    for item in order_items:
        items_by_order.setdefault(item.order_id, []).append(item)

    payments_by_order = {}
    for payment in payments:
        payments_by_order.setdefault(payment.order_id, []).append(payment)

    customer_ids = {order.customer_id for order in orders_by_id.values() if order.customer_id}
    customer_users = {
        user.id: user for user in User.query.filter(User.id.in_(customer_ids)).all()
    } if customer_ids else {}

    address_ids = {order.shipping_address_id for order in orders_by_id.values() if order.shipping_address_id}
    addresses = {
        address.id: address for address in Address.query.filter(Address.id.in_(address_ids)).all()
    } if address_ids else {}

    vendor_ids = {item.vendor_id for item in order_items if item.vendor_id}
    vendor_profiles = {
        vendor.id: vendor for vendor in VendorProfile.query.filter(VendorProfile.id.in_(vendor_ids)).all()
    } if vendor_ids else {}

    product_ids = {item.product_id for item in order_items if item.product_id}
    products = {
        product.id: product for product in Product.query.filter(Product.id.in_(product_ids)).all()
    } if product_ids else {}

    category_ids = {product.category_id for product in products.values() if product.category_id}
    categories = {
        category.id: category for category in Category.query.filter(Category.id.in_(category_ids)).all()
    } if category_ids else {}

    delivery_profile_ids = {shipment.assigned_delivery_boy_id for shipment in ranged_shipments if shipment.assigned_delivery_boy_id}
    delivery_profiles = {
        profile.id: profile for profile in DeliveryProfile.query.filter(DeliveryProfile.id.in_(delivery_profile_ids)).all()
    } if delivery_profile_ids else {}

    logistics_profile_ids = {shipment.logistics_id for shipment in ranged_shipments if shipment.logistics_id}
    logistics_profiles = {
        profile.id: profile for profile in LogisticsProfile.query.filter(LogisticsProfile.id.in_(logistics_profile_ids)).all()
    } if logistics_profile_ids else {}

    admin_user_ids = {shipment.assigned_by_logistics_id for shipment in ranged_shipments if shipment.assigned_by_logistics_id}
    delivery_user_ids = {profile.user_id for profile in delivery_profiles.values() if profile.user_id}
    logistics_user_ids = {profile.user_id for profile in logistics_profiles.values() if profile.user_id}
    related_user_ids = customer_ids | admin_user_ids | delivery_user_ids | logistics_user_ids
    related_users = {
        user.id: user for user in User.query.filter(User.id.in_(related_user_ids)).all()
    } if related_user_ids else {}

    total_revenue = sum(float(order.total_amount or 0) for order in valid_orders)
    total_items = sum(int(item.quantity or 0) for item in order_items if item.order_id in valid_order_ids)
    delivered_shipments = [shipment for shipment in ranged_shipments if shipment.shipment_status == "delivered"]
    total_deliveries = len(delivered_shipments)

    avg_revenue_per_item = (total_revenue / total_items) if total_items else 0.0
    avg_revenue_per_delivery = (total_revenue / total_deliveries) if total_deliveries else 0.0

    vendor_stats = {}
    for item in order_items:
        if item.order_id not in valid_order_ids:
            continue
        revenue = float(item.price or 0) * int(item.quantity or 0)
        stat = vendor_stats.setdefault(
            item.vendor_id,
            {"vendor_id": item.vendor_id, "total_revenue": 0.0, "total_items": 0, "order_ids": set()},
        )
        stat["total_revenue"] += revenue
        stat["total_items"] += int(item.quantity or 0)
        stat["order_ids"].add(item.order_id)

    top_vendors = []
    for stat in vendor_stats.values():
        profile = vendor_profiles.get(stat["vendor_id"])
        top_vendors.append(
            {
                "vendor_id": stat["vendor_id"],
                "store_name": profile.store_name if profile else f"Vendor #{stat['vendor_id']}",
                "total_revenue": _to_float(stat["total_revenue"]),
                "total_items": int(stat["total_items"]),
                "total_deliveries": len(stat["order_ids"]),
            }
        )
    top_vendors.sort(key=lambda row: row["total_revenue"], reverse=True)
    top_vendors = top_vendors[:10]

    delivery_stats = {}
    for shipment in ranged_shipments:
        if not shipment.assigned_delivery_boy_id:
            continue
        stat = delivery_stats.setdefault(
            shipment.assigned_delivery_boy_id,
            {"profile_id": shipment.assigned_delivery_boy_id, "total_deliveries": 0, "delivered": 0, "failed": 0, "revenue": 0.0},
        )
        stat["total_deliveries"] += 1
        if shipment.shipment_status == "delivered":
            stat["delivered"] += 1
        if shipment.shipment_status == "failed":
            stat["failed"] += 1
        order = orders_by_id.get(shipment.order_id)
        if order and order.id in valid_order_ids:
            stat["revenue"] += float(order.total_amount or 0)

    top_delivery_boys = []
    for stat in delivery_stats.values():
        profile = delivery_profiles.get(stat["profile_id"])
        rider_user = related_users.get(profile.user_id) if profile else None
        top_delivery_boys.append(
            {
                "profile_id": stat["profile_id"],
                "name": rider_user.name if rider_user else f"Delivery #{stat['profile_id']}",
                "email": rider_user.email if rider_user else None,
                "total_deliveries": int(stat["total_deliveries"]),
                "delivered": int(stat["delivered"]),
                "failed": int(stat["failed"]),
                "total_revenue": _to_float(stat["revenue"]),
            }
        )
    top_delivery_boys.sort(key=lambda row: (row["delivered"], row["total_deliveries"], row["total_revenue"]), reverse=True)
    top_delivery_boys = top_delivery_boys[:10]

    customer_stats = {}
    for order in valid_orders:
        stat = customer_stats.setdefault(
            order.customer_id,
            {"customer_id": order.customer_id, "orders": 0, "total_spend": 0.0, "items": 0},
        )
        stat["orders"] += 1
        stat["total_spend"] += float(order.total_amount or 0)
        for item in items_by_order.get(order.id, []):
            stat["items"] += int(item.quantity or 0)

    top_customers = []
    for stat in customer_stats.values():
        customer = customer_users.get(stat["customer_id"])
        top_customers.append(
            {
                "customer_id": stat["customer_id"],
                "name": customer.name if customer else f"Customer #{stat['customer_id']}",
                "email": customer.email if customer else None,
                "total_orders": int(stat["orders"]),
                "total_items": int(stat["items"]),
                "total_spend": _to_float(stat["total_spend"]),
            }
        )
    top_customers.sort(key=lambda row: row["total_spend"], reverse=True)
    top_customers = top_customers[:10]

    item_stats = {}
    category_stats = {}
    for item in order_items:
        if item.order_id not in valid_order_ids:
            continue
        product = products.get(item.product_id)
        revenue = float(item.price or 0) * int(item.quantity or 0)

        item_stat = item_stats.setdefault(
            item.product_id,
            {"product_id": item.product_id, "qty": 0, "revenue": 0.0, "order_ids": set()},
        )
        item_stat["qty"] += int(item.quantity or 0)
        item_stat["revenue"] += revenue
        item_stat["order_ids"].add(item.order_id)

        category_id = product.category_id if product else None
        if category_id:
            category_stat = category_stats.setdefault(
                category_id,
                {"category_id": category_id, "qty": 0, "revenue": 0.0, "order_ids": set()},
            )
            category_stat["qty"] += int(item.quantity or 0)
            category_stat["revenue"] += revenue
            category_stat["order_ids"].add(item.order_id)

    top_items = []
    for stat in item_stats.values():
        product = products.get(stat["product_id"])
        top_items.append(
            {
                "product_id": stat["product_id"],
                "name": product.name if product else f"Item #{stat['product_id']}",
                "sku": product.sku if product else None,
                "category": categories.get(product.category_id).name if product and categories.get(product.category_id) else None,
                "total_qty": int(stat["qty"]),
                "total_revenue": _to_float(stat["revenue"]),
                "total_deliveries": len(stat["order_ids"]),
            }
        )
    top_items.sort(key=lambda row: row["total_revenue"], reverse=True)
    top_items = top_items[:10]

    top_categories = []
    for stat in category_stats.values():
        category = categories.get(stat["category_id"])
        top_categories.append(
            {
                "category_id": stat["category_id"],
                "name": category.name if category else f"Category #{stat['category_id']}",
                "total_qty": int(stat["qty"]),
                "total_revenue": _to_float(stat["revenue"]),
                "total_deliveries": len(stat["order_ids"]),
            }
        )
    top_categories.sort(key=lambda row: row["total_revenue"], reverse=True)
    top_categories = top_categories[:10]

    detailed_rows = []
    for shipment in ranged_shipments:
        order = orders_by_id.get(shipment.order_id)
        if not order:
            continue
        customer = customer_users.get(order.customer_id)
        address = addresses.get(order.shipping_address_id)
        item_rows = items_by_order.get(order.id, [])
        payment_rows = payments_by_order.get(order.id, [])
        item_count = sum(int(item.quantity or 0) for item in item_rows)

        vendor_names = []
        item_names = []
        for item in item_rows:
            vendor = vendor_profiles.get(item.vendor_id)
            product = products.get(item.product_id)
            vendor_names.append(vendor.store_name if vendor else f"Vendor #{item.vendor_id}")
            item_names.append(product.name if product else f"Item #{item.product_id}")

        logistics_profile = logistics_profiles.get(shipment.logistics_id)
        logistics_user = related_users.get(logistics_profile.user_id) if logistics_profile else None
        approver_user = related_users.get(shipment.assigned_by_logistics_id)
        delivery_profile = delivery_profiles.get(shipment.assigned_delivery_boy_id)
        delivery_user = related_users.get(delivery_profile.user_id) if delivery_profile else None

        payment_status = payment_rows[0].payment_status if payment_rows else order.payment_status
        payment_method = payment_rows[0].payment_method if payment_rows else None

        row = {
            "shipment_id": shipment.id,
            "tracking_number": shipment.tracking_number,
            "shipment_status": shipment.shipment_status,
            "order_id": order.id,
            "order_status": order.order_status,
            "order_total": _to_float(order.total_amount),
            "payment_status": payment_status,
            "payment_method": payment_method,
            "item_count": int(item_count),
            "items": ", ".join(sorted(set(item_names))),
            "vendors": ", ".join(sorted(set(vendor_names))),
            "customer_name": customer.name if customer else (address.full_name if address else "-"),
            "customer_email": customer.email if customer else None,
            "customer_phone": address.phone if address else None,
            "customer_address": (
                ", ".join(part for part in [address.address_line_1, address.address_line_2, address.city, address.state, address.postal_code] if part)
                if address
                else None
            ),
            "logistics_owner": logistics_user.name if logistics_user else None,
            "approved_by_logistics": approver_user.name if approver_user else None,
            "delivery_boy": delivery_user.name if delivery_user else None,
            "assigned_time": shipment.assigned_time.isoformat() + "Z" if shipment.assigned_time else None,
            "pickup_time": shipment.pickup_time.isoformat() + "Z" if shipment.pickup_time else None,
            "delivery_time": shipment.delivery_time.isoformat() + "Z" if shipment.delivery_time else None,
            "failure_reason": shipment.failure_reason,
            "created_at": shipment.created_at.isoformat() + "Z" if shipment.created_at else None,
        }
        detailed_rows.append(row)

    if search_q:
        filtered_rows = []
        for row in detailed_rows:
            text = " ".join(
                str(value or "")
                for value in [
                    row["tracking_number"],
                    row["shipment_status"],
                    row["order_id"],
                    row["customer_name"],
                    row["customer_email"],
                    row["delivery_boy"],
                    row["logistics_owner"],
                    row["approved_by_logistics"],
                    row["vendors"],
                    row["items"],
                    row["payment_status"],
                ]
            ).lower()
            if search_q in text:
                filtered_rows.append(row)
        detailed_rows = filtered_rows

    detailed_rows = detailed_rows[:250]

    trend = _build_revenue_trend(valid_orders, valid_order_ids, items_by_order, ranged_shipments, start, end)

    return jsonify(
        {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "filter": {
                "range": period["range"],
                "start": start.isoformat() + "Z",
                "end": (end - timedelta(seconds=1)).isoformat() + "Z",
                "query": search_q,
            },
            "totals": {
                "revenue": _to_float(total_revenue),
                "deliveries": int(total_deliveries),
                "items": int(total_items),
                "avg_revenue_per_item": _to_float(avg_revenue_per_item),
                "avg_revenue_per_delivery": _to_float(avg_revenue_per_delivery),
            },
            "top_vendors": top_vendors,
            "top_delivery_boys": top_delivery_boys,
            "top_customers": top_customers,
            "top_items": top_items,
            "top_categories": top_categories,
            "revenue_trend": trend,
            "deliveries": detailed_rows,
        }
    )
