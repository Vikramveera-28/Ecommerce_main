from __future__ import annotations

from datetime import datetime, timedelta

from app.admin.report_utils import build_revenue_trend, to_float
from app.common.mongo_utils import as_datetime, load_collection
from app.models import OrderStatus, PaymentStatus


def _get(document, key, default=None):
    if document is None:
        return default
    if isinstance(document, dict):
        return document.get(key, default)
    return getattr(document, key, default)


def _doc_id(document):
    return _get(document, "id", _get(document, "_id"))


def build_sales_report(mongo_db) -> dict:
    orders = load_collection(mongo_db, "orders")
    payments = load_collection(mongo_db, "payments")
    order_items = load_collection(mongo_db, "order_items")
    vendors = {_doc_id(vendor): vendor for vendor in load_collection(mongo_db, "vendor_profiles")}

    total_orders = len(orders)
    total_revenue = sum(float(_get(order, "total_amount", 0) or 0) for order in orders)

    cod_pending = sum(1 for payment in payments if _get(payment, "payment_status") == PaymentStatus.COD_PENDING.value)
    cod_confirmed = sum(1 for payment in payments if _get(payment, "payment_status") == PaymentStatus.COD_CONFIRMED.value)

    by_status: dict[str, int] = {}
    for order in orders:
        status = _get(order, "order_status") or "unknown"
        by_status[status] = by_status.get(status, 0) + 1

    vendor_sales: dict[int, float] = {}
    for item in order_items:
        order = next((row for row in orders if _doc_id(row) == _get(item, "order_id")), None)
        if not order or _get(order, "order_status") == OrderStatus.CANCELLED.value:
            continue
        revenue = float(_get(item, "price", 0) or 0) * int(_get(item, "quantity", 0) or 0)
        vendor_id = _get(item, "vendor_id")
        vendor_sales[vendor_id] = vendor_sales.get(vendor_id, 0.0) + revenue

    top_vendors = []
    for vendor_id, gross_sales in sorted(vendor_sales.items(), key=lambda row: row[1], reverse=True)[:10]:
        vendor = vendors.get(vendor_id)
        top_vendors.append(
            {
                "vendor_id": vendor_id,
                "store_name": _get(vendor, "store_name", f"Vendor #{vendor_id}"),
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
    users = {_doc_id(user): user for user in load_collection(mongo_db, "users")}
    addresses = {_doc_id(address): address for address in load_collection(mongo_db, "addresses")}
    vendor_profiles = {_doc_id(vendor): vendor for vendor in load_collection(mongo_db, "vendor_profiles")}
    products = {_doc_id(product): product for product in load_collection(mongo_db, "products")}
    categories = {_doc_id(category): category for category in load_collection(mongo_db, "categories")}
    delivery_profiles = {_doc_id(profile): profile for profile in load_collection(mongo_db, "delivery_profiles")}
    logistics_profiles = {_doc_id(profile): profile for profile in load_collection(mongo_db, "logistics_profiles")}

    ranged_orders = [
        order
        for order in orders
        if (created_at := as_datetime(_get(order, "created_at"))) is not None and start <= created_at < end
    ]
    ranged_orders.sort(key=lambda order: as_datetime(_get(order, "created_at")) or datetime.min, reverse=True)

    valid_orders = [order for order in ranged_orders if _get(order, "order_status") != OrderStatus.CANCELLED.value]
    valid_order_ids = {_doc_id(order) for order in valid_orders}

    ranged_shipments = [
        shipment
        for shipment in shipments
        if (created_at := as_datetime(_get(shipment, "created_at"))) is not None and start <= created_at < end
    ]
    ranged_shipments.sort(key=lambda shipment: as_datetime(_get(shipment, "created_at")) or datetime.min, reverse=True)

    shipment_order_ids = {_get(shipment, "order_id") for shipment in ranged_shipments}
    all_relevant_order_ids = valid_order_ids | shipment_order_ids

    scoped_items = [item for item in order_items if _get(item, "order_id") in all_relevant_order_ids]
    scoped_payments = [payment for payment in payments if _get(payment, "order_id") in all_relevant_order_ids]

    orders_by_id = {_doc_id(order): order for order in ranged_orders}
    for order in orders:
        order_id = _doc_id(order)
        if order_id in all_relevant_order_ids and order_id not in orders_by_id:
            orders_by_id[order_id] = order

    items_by_order: dict[int, list] = {}
    for item in scoped_items:
        items_by_order.setdefault(_get(item, "order_id"), []).append(item)

    payments_by_order: dict[int, list] = {}
    for payment in scoped_payments:
        payments_by_order.setdefault(_get(payment, "order_id"), []).append(payment)

    customer_ids = {_get(order, "customer_id") for order in orders_by_id.values() if _get(order, "customer_id")}
    customer_users = {user_id: users[user_id] for user_id in customer_ids if user_id in users}

    total_revenue = sum(float(_get(order, "total_amount", 0) or 0) for order in valid_orders)
    total_items = sum(int(_get(item, "quantity", 0) or 0) for item in scoped_items if _get(item, "order_id") in valid_order_ids)
    delivered_shipments = [shipment for shipment in ranged_shipments if _get(shipment, "shipment_status") == "delivered"]
    total_deliveries = len(delivered_shipments)

    avg_revenue_per_item = (total_revenue / total_items) if total_items else 0.0
    avg_revenue_per_delivery = (total_revenue / total_deliveries) if total_deliveries else 0.0

    vendor_stats: dict[int, dict] = {}
    for item in scoped_items:
        if _get(item, "order_id") not in valid_order_ids:
            continue
        revenue = float(_get(item, "price", 0) or 0) * int(_get(item, "quantity", 0) or 0)
        stat = vendor_stats.setdefault(
            _get(item, "vendor_id"),
            {"vendor_id": _get(item, "vendor_id"), "total_revenue": 0.0, "total_items": 0, "order_ids": set()},
        )
        stat["total_revenue"] += revenue
        stat["total_items"] += int(_get(item, "quantity", 0) or 0)
        stat["order_ids"].add(_get(item, "order_id"))

    top_vendors = []
    for stat in vendor_stats.values():
        profile = vendor_profiles.get(stat["vendor_id"])
        top_vendors.append(
            {
                "vendor_id": stat["vendor_id"],
                "store_name": _get(profile, "store_name", f"Vendor #{stat['vendor_id']}"),
                "total_revenue": to_float(stat["total_revenue"]),
                "total_items": int(stat["total_items"]),
                "total_deliveries": len(stat["order_ids"]),
            }
        )
    top_vendors.sort(key=lambda row: row["total_revenue"], reverse=True)
    top_vendors = top_vendors[:10]

    delivery_stats: dict[int, dict] = {}
    for shipment in ranged_shipments:
        if not _get(shipment, "assigned_delivery_boy_id"):
            continue
        stat = delivery_stats.setdefault(
            _get(shipment, "assigned_delivery_boy_id"),
            {"profile_id": _get(shipment, "assigned_delivery_boy_id"), "total_deliveries": 0, "delivered": 0, "failed": 0, "revenue": 0.0},
        )
        stat["total_deliveries"] += 1
        if _get(shipment, "shipment_status") == "delivered":
            stat["delivered"] += 1
        if _get(shipment, "shipment_status") == "failed":
            stat["failed"] += 1
        order = orders_by_id.get(_get(shipment, "order_id"))
        if order and _doc_id(order) in valid_order_ids:
            stat["revenue"] += float(_get(order, "total_amount", 0) or 0)

    top_delivery_boys = []
    for stat in delivery_stats.values():
        profile = delivery_profiles.get(stat["profile_id"])
        rider_user = users.get(_get(profile, "user_id")) if profile else None
        top_delivery_boys.append(
            {
                "profile_id": stat["profile_id"],
                "name": _get(rider_user, "name", f"Delivery #{stat['profile_id']}"),
                "email": _get(rider_user, "email"),
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
        customer_id = _get(order, "customer_id")
        stat = customer_stats.setdefault(customer_id, {"customer_id": customer_id, "orders": 0, "total_spend": 0.0, "items": 0})
        stat["orders"] += 1
        stat["total_spend"] += float(_get(order, "total_amount", 0) or 0)
        for item in items_by_order.get(_doc_id(order), []):
            stat["items"] += int(_get(item, "quantity", 0) or 0)

    top_customers = []
    for stat in customer_stats.values():
        customer = customer_users.get(stat["customer_id"])
        top_customers.append(
            {
                "customer_id": stat["customer_id"],
                "name": _get(customer, "name", f"Customer #{stat['customer_id']}"),
                "email": _get(customer, "email"),
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
        if _get(item, "order_id") not in valid_order_ids:
            continue
        product = products.get(_get(item, "product_id"))
        revenue = float(_get(item, "price", 0) or 0) * int(_get(item, "quantity", 0) or 0)

        item_stat = item_stats.setdefault(
            _get(item, "product_id"),
            {"product_id": _get(item, "product_id"), "qty": 0, "revenue": 0.0, "order_ids": set()},
        )
        item_stat["qty"] += int(_get(item, "quantity", 0) or 0)
        item_stat["revenue"] += revenue
        item_stat["order_ids"].add(_get(item, "order_id"))

        category_id = _get(product, "category_id") if product else None
        if category_id:
            category_stat = category_stats.setdefault(
                category_id,
                {"category_id": category_id, "qty": 0, "revenue": 0.0, "order_ids": set()},
            )
            category_stat["qty"] += int(_get(item, "quantity", 0) or 0)
            category_stat["revenue"] += revenue
            category_stat["order_ids"].add(_get(item, "order_id"))

    top_items = []
    for stat in item_stats.values():
        product = products.get(stat["product_id"])
        category = categories.get(_get(product, "category_id")) if product else None
        top_items.append(
            {
                "product_id": stat["product_id"],
                "name": _get(product, "name", f"Item #{stat['product_id']}"),
                "sku": _get(product, "sku"),
                "category": _get(category, "name"),
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
                "name": _get(category, "name", f"Category #{stat['category_id']}"),
                "total_qty": int(stat["qty"]),
                "total_revenue": _to_float(stat["revenue"]),
                "total_deliveries": len(stat["order_ids"]),
            }
        )
    top_categories.sort(key=lambda row: row["total_revenue"], reverse=True)
    top_categories = top_categories[:10]

    detailed_rows = []
    for shipment in ranged_shipments:
        order = orders_by_id.get(_get(shipment, "order_id"))
        if not order:
            continue
        customer = customer_users.get(_get(order, "customer_id"))
        address = addresses.get(_get(order, "shipping_address_id"))
        item_rows = items_by_order.get(_doc_id(order), [])
        payment_rows = payments_by_order.get(_doc_id(order), [])
        item_count = sum(int(_get(item, "quantity", 0) or 0) for item in item_rows)

        vendor_names = []
        item_names = []
        for item in item_rows:
            vendor = vendor_profiles.get(_get(item, "vendor_id"))
            product = products.get(_get(item, "product_id"))
            vendor_names.append(_get(vendor, "store_name", f"Vendor #{_get(item, 'vendor_id')}"))
            item_names.append(_get(product, "name", f"Item #{_get(item, 'product_id')}"))

        logistics_profile = logistics_profiles.get(_get(shipment, "logistics_id"))
        logistics_user = users.get(_get(logistics_profile, "user_id")) if logistics_profile else None
        approver_user = users.get(_get(shipment, "assigned_by_logistics_id"))
        delivery_profile = delivery_profiles.get(_get(shipment, "assigned_delivery_boy_id"))
        delivery_user = users.get(_get(delivery_profile, "user_id")) if delivery_profile else None

        payment_status = _get(payment_rows[0], "payment_status") if payment_rows else _get(order, "payment_status")
        payment_method = _get(payment_rows[0], "payment_method") if payment_rows else None

        row = {
            "shipment_id": _doc_id(shipment),
            "tracking_number": _get(shipment, "tracking_number"),
            "shipment_status": _get(shipment, "shipment_status"),
            "order_id": _doc_id(order),
            "order_status": _get(order, "order_status"),
            "order_total": _to_float(_get(order, "total_amount")),
            "payment_status": payment_status,
            "payment_method": payment_method,
            "item_count": int(item_count),
            "items": ", ".join(sorted(set(item_names))),
            "vendors": ", ".join(sorted(set(vendor_names))),
            "customer_name": _get(customer, "name", _get(address, "full_name", "-")),
            "customer_email": _get(customer, "email"),
            "customer_phone": _get(address, "phone"),
            "customer_address": (
                ", ".join(
                    part
                    for part in [
                        _get(address, "address_line_1"),
                        _get(address, "address_line_2"),
                        _get(address, "city"),
                        _get(address, "state"),
                        _get(address, "postal_code"),
                    ]
                    if part
                )
                if address
                else None
            ),
            "logistics_owner": _get(logistics_user, "name"),
            "approved_by_logistics": _get(approver_user, "name"),
            "delivery_boy": _get(delivery_user, "name"),
            "assigned_time": _iso_or_none(_get(shipment, "assigned_time")),
            "pickup_time": _iso_or_none(_get(shipment, "pickup_time")),
            "delivery_time": _iso_or_none(_get(shipment, "delivery_time")),
            "failure_reason": _get(shipment, "failure_reason"),
            "created_at": _iso_or_none(_get(shipment, "created_at")),
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
