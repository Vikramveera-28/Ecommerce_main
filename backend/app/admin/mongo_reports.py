from __future__ import annotations

from datetime import datetime, timedelta

from app.admin.report_utils import build_revenue_trend, to_float
from app.common.mongo_utils import as_datetime, load_collection
from app.models import OrderStatus, PaymentStatus


def build_sales_report(mongo_db) -> dict:
    orders = load_collection(mongo_db, "orders")
    payments = load_collection(mongo_db, "payments")
    order_items = load_collection(mongo_db, "order_items")
    vendors = {vendor.id: vendor for vendor in load_collection(mongo_db, "vendor_profiles")}

    total_orders = len(orders)
    total_revenue = sum(float(order.total_amount or 0) for order in orders)

    cod_pending = sum(1 for payment in payments if payment.payment_status == PaymentStatus.COD_PENDING.value)
    cod_confirmed = sum(1 for payment in payments if payment.payment_status == PaymentStatus.COD_CONFIRMED.value)

    by_status: dict[str, int] = {}
    for order in orders:
        status = order.order_status or "unknown"
        by_status[status] = by_status.get(status, 0) + 1

    vendor_sales: dict[int, float] = {}
    for item in order_items:
        order = next((row for row in orders if row.id == item.order_id), None)
        if not order or order.order_status == OrderStatus.CANCELLED.value:
            continue
        revenue = float(item.price or 0) * int(item.quantity or 0)
        vendor_sales[item.vendor_id] = vendor_sales.get(item.vendor_id, 0.0) + revenue

    top_vendors = []
    for vendor_id, gross_sales in sorted(vendor_sales.items(), key=lambda row: row[1], reverse=True)[:10]:
        vendor = vendors.get(vendor_id)
        top_vendors.append(
            {
                "vendor_id": vendor_id,
                "store_name": vendor.store_name if vendor else f"Vendor #{vendor_id}",
                "gross_sales": float(round(gross_sales, 2)),
            }
        )

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "totals": {
            "orders": int(total_orders),
            "revenue": float(round(total_revenue, 2)),
            "cod_pending_orders": int(cod_pending),
            "cod_confirmed_orders": int(cod_confirmed),
        },
        "orders_by_status": by_status,
        "top_vendors": top_vendors,
    }


def build_operations_report(mongo_db, *, range_key: str, start: datetime, end: datetime, search_q: str) -> dict:
    orders = load_collection(mongo_db, "orders")
    shipments = load_collection(mongo_db, "shipments")
    order_items = load_collection(mongo_db, "order_items")
    payments = load_collection(mongo_db, "payments")
    users = {user.id: user for user in load_collection(mongo_db, "users")}
    addresses = {address.id: address for address in load_collection(mongo_db, "addresses")}
    vendor_profiles = {vendor.id: vendor for vendor in load_collection(mongo_db, "vendor_profiles")}
    products = {product.id: product for product in load_collection(mongo_db, "products")}
    categories = {category.id: category for category in load_collection(mongo_db, "categories")}
    delivery_profiles = {profile.id: profile for profile in load_collection(mongo_db, "delivery_profiles")}
    logistics_profiles = {profile.id: profile for profile in load_collection(mongo_db, "logistics_profiles")}

    ranged_orders = [
        order
        for order in orders
        if (created_at := as_datetime(order.created_at)) is not None and start <= created_at < end
    ]
    ranged_orders.sort(key=lambda order: as_datetime(order.created_at) or datetime.min, reverse=True)

    valid_orders = [order for order in ranged_orders if order.order_status != OrderStatus.CANCELLED.value]
    valid_order_ids = {order.id for order in valid_orders}

    ranged_shipments = [
        shipment
        for shipment in shipments
        if (created_at := as_datetime(shipment.created_at)) is not None and start <= created_at < end
    ]
    ranged_shipments.sort(key=lambda shipment: as_datetime(shipment.created_at) or datetime.min, reverse=True)

    shipment_order_ids = {shipment.order_id for shipment in ranged_shipments}
    all_relevant_order_ids = valid_order_ids | shipment_order_ids

    scoped_items = [item for item in order_items if item.order_id in all_relevant_order_ids]
    scoped_payments = [payment for payment in payments if payment.order_id in all_relevant_order_ids]

    orders_by_id = {order.id: order for order in ranged_orders}
    for order in orders:
        if order.id in all_relevant_order_ids and order.id not in orders_by_id:
            orders_by_id[order.id] = order

    items_by_order: dict[int, list] = {}
    for item in scoped_items:
        items_by_order.setdefault(item.order_id, []).append(item)

    payments_by_order: dict[int, list] = {}
    for payment in scoped_payments:
        payments_by_order.setdefault(payment.order_id, []).append(payment)

    customer_ids = {order.customer_id for order in orders_by_id.values() if order.customer_id}
    customer_users = {user_id: users[user_id] for user_id in customer_ids if user_id in users}

    total_revenue = sum(float(order.total_amount or 0) for order in valid_orders)
    total_items = sum(int(item.quantity or 0) for item in scoped_items if item.order_id in valid_order_ids)
    delivered_shipments = [shipment for shipment in ranged_shipments if shipment.shipment_status == "delivered"]
    total_deliveries = len(delivered_shipments)

    avg_revenue_per_item = (total_revenue / total_items) if total_items else 0.0
    avg_revenue_per_delivery = (total_revenue / total_deliveries) if total_deliveries else 0.0

    vendor_stats: dict[int, dict] = {}
    for item in scoped_items:
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
                "total_revenue": to_float(stat["total_revenue"]),
                "total_items": int(stat["total_items"]),
                "total_deliveries": len(stat["order_ids"]),
            }
        )
    top_vendors.sort(key=lambda row: row["total_revenue"], reverse=True)
    top_vendors = top_vendors[:10]

    delivery_stats: dict[int, dict] = {}
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
        rider_user = users.get(profile.user_id) if profile else None
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

    customer_stats: dict[int, dict] = {}
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
                "total_spend": to_float(stat["total_spend"]),
            }
        )
    top_customers.sort(key=lambda row: row["total_spend"], reverse=True)
    top_customers = top_customers[:10]

    item_stats: dict[int, dict] = {}
    category_stats: dict[int, dict] = {}
    for item in scoped_items:
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
        category = categories.get(product.category_id) if product else None
        top_items.append(
            {
                "product_id": stat["product_id"],
                "name": product.name if product else f"Item #{stat['product_id']}",
                "sku": product.sku if product else None,
                "category": category.name if category else None,
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
        logistics_user = users.get(logistics_profile.user_id) if logistics_profile else None
        approver_user = users.get(shipment.assigned_by_logistics_id)
        delivery_profile = delivery_profiles.get(shipment.assigned_delivery_boy_id)
        delivery_user = users.get(delivery_profile.user_id) if delivery_profile else None

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
                ", ".join(
                    part
                    for part in [
                        getattr(address, "address_line_1", None),
                        getattr(address, "address_line_2", None),
                        getattr(address, "city", None),
                        getattr(address, "state", None),
                        getattr(address, "postal_code", None),
                    ]
                    if part
                )
                if address
                else None
            ),
            "logistics_owner": logistics_user.name if logistics_user else None,
            "approved_by_logistics": approver_user.name if approver_user else None,
            "delivery_boy": delivery_user.name if delivery_user else None,
            "assigned_time": _iso_or_none(shipment.assigned_time),
            "pickup_time": _iso_or_none(shipment.pickup_time),
            "delivery_time": _iso_or_none(shipment.delivery_time),
            "failure_reason": shipment.failure_reason,
            "created_at": _iso_or_none(shipment.created_at),
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

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "filter": {
            "range": range_key,
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


def _iso_or_none(value) -> str | None:
    parsed = as_datetime(value)
    if parsed is not None:
        return parsed.isoformat() + "Z"
    if isinstance(value, str) and value:
        return value if value.endswith("Z") else value + "Z"
    return None
