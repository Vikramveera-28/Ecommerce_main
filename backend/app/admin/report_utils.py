from datetime import datetime, timedelta


def to_float(value):
    return float(round(float(value or 0), 2))


def build_revenue_trend(valid_orders, valid_order_ids, items_by_order, shipments, start, end):
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
            "revenue": to_float(bucket["revenue"]),
            "items": int(bucket["items"]),
            "deliveries": int(bucket["deliveries"]),
        }
        for bucket in buckets
    ]
