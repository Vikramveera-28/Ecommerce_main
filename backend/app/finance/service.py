from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from uuid import uuid4

from app.extensions import db
from app.models import (
    Commission,
    DeliveryProfile,
    LedgerActorType,
    LedgerDirection,
    LedgerEntry,
    LedgerSourceType,
    LedgerStatus,
    LogisticsProfile,
    Order,
    OrderItem,
    Payout,
    PayoutStatus,
    Role,
    Shipment,
    ShipmentStatus,
    User,
    VendorProfile,
)


DEFAULT_CURRENCY = "INR"
DEFAULT_COMMISSION_PERCENTAGE = 10.0
DELIVERY_RATE_PER_DELIVERY = 85.0
DELIVERY_RATE_PER_ITEM = 12.0
LOGISTICS_RATE_PER_SHIPMENT = 30.0


def iso_or_none(value):
    return value.isoformat() if value else None


def round_amount(value):
    return float(round(float(value or 0), 2))


def signed_amount(entry: LedgerEntry) -> float:
    amount = round_amount(entry.amount)
    return amount if entry.direction == LedgerDirection.CREDIT.value else -amount


def apply_actor_scope(query, actor_type: str, actor_id: int | None):
    query = query.filter(LedgerEntry.actor_type == actor_type)
    if actor_id is None:
        return query.filter(LedgerEntry.actor_id.is_(None))
    return query.filter(LedgerEntry.actor_id == actor_id)


def apply_payout_actor_scope(query, actor_type: str, actor_id: int | None):
    query = query.filter(Payout.actor_type == actor_type)
    if actor_id is None:
        return query.filter(Payout.actor_id.is_(None))
    return query.filter(Payout.actor_id == actor_id)


def ensure_commission_for_order_item(order_item: OrderItem) -> Commission:
    commission = Commission.query.filter_by(order_item_id=order_item.id).first()
    if commission:
        return commission

    gross_amount = round_amount((order_item.price or 0) * (order_item.quantity or 0))
    platform_commission = round_amount(gross_amount * (DEFAULT_COMMISSION_PERCENTAGE / 100.0))
    vendor_amount = round_amount(gross_amount - platform_commission)
    commission = Commission(
        order_item_id=order_item.id,
        vendor_amount=vendor_amount,
        platform_commission=platform_commission,
        commission_percentage=DEFAULT_COMMISSION_PERCENTAGE,
    )
    db.session.add(commission)
    db.session.flush()
    return commission


def resolve_finance_actor(user: User) -> dict:
    if user.role == Role.VENDOR.value:
        profile = VendorProfile.query.filter_by(user_id=user.id).first()
        if not profile:
            raise ValueError("Vendor profile not found")
        return {
            "actor_type": LedgerActorType.VENDOR.value,
            "actor_id": profile.id,
            "name": profile.store_name or user.name,
            "email": user.email,
            "user_id": user.id,
        }

    if user.role == Role.DELIVERY_BOY.value:
        profile = DeliveryProfile.query.filter_by(user_id=user.id).first()
        if not profile or not profile.is_active:
            raise ValueError("Delivery profile not found or inactive")
        return {
            "actor_type": LedgerActorType.DELIVERY_BOY.value,
            "actor_id": profile.id,
            "name": user.name,
            "email": user.email,
            "user_id": user.id,
        }

    if user.role == Role.LOGISTICS.value:
        profile = LogisticsProfile.query.filter_by(user_id=user.id).first()
        if not profile:
            raise ValueError("Logistics profile not found")
        return {
            "actor_type": LedgerActorType.LOGISTICS.value,
            "actor_id": profile.id,
            "name": user.name,
            "email": user.email,
            "user_id": user.id,
        }

    if user.role == Role.ADMIN.value:
        return {
            "actor_type": LedgerActorType.PLATFORM.value,
            "actor_id": None,
            "name": "Platform",
            "email": user.email,
            "user_id": user.id,
        }

    raise ValueError("This role does not have a finance workspace")


def resolve_actor_identity(actor_type: str, actor_id: int | None) -> dict:
    if actor_type == LedgerActorType.PLATFORM.value:
        return {
            "actor_type": actor_type,
            "actor_id": None,
            "name": "Platform",
            "email": None,
            "user_id": None,
            "secondary_label": "Unified platform ledger",
        }

    if actor_type == LedgerActorType.VENDOR.value:
        profile = VendorProfile.query.get(actor_id) if actor_id is not None else None
        if not profile or not profile.user:
            raise ValueError("Vendor actor not found")
        return {
            "actor_type": actor_type,
            "actor_id": profile.id,
            "name": profile.store_name or profile.user.name,
            "email": profile.user.email,
            "user_id": profile.user_id,
            "secondary_label": profile.user.name,
        }

    if actor_type == LedgerActorType.DELIVERY_BOY.value:
        profile = DeliveryProfile.query.get(actor_id) if actor_id is not None else None
        if not profile or not profile.user:
            raise ValueError("Delivery actor not found")
        return {
            "actor_type": actor_type,
            "actor_id": profile.id,
            "name": profile.user.name,
            "email": profile.user.email,
            "user_id": profile.user_id,
            "secondary_label": profile.phone or profile.user.phone,
        }

    if actor_type == LedgerActorType.LOGISTICS.value:
        profile = LogisticsProfile.query.get(actor_id) if actor_id is not None else None
        if not profile or not profile.user:
            raise ValueError("Logistics actor not found")
        return {
            "actor_type": actor_type,
            "actor_id": profile.id,
            "name": profile.user.name,
            "email": profile.user.email,
            "user_id": profile.user_id,
            "secondary_label": profile.service_area or profile.vehicle_number,
        }

    raise ValueError("Unsupported actor type")


def _build_reference_key(actor_type: str, actor_id: int | None, source_type: str, source_id: int | None, entry_code: str) -> str:
    actor_token = "platform" if actor_id is None else str(actor_id)
    source_token = "none" if source_id is None else str(source_id)
    return f"{source_type}:{source_token}:{actor_type}:{actor_token}:{entry_code}"


def ensure_system_ledger_entry(
    *,
    actor_type: str,
    actor_id: int | None,
    source_type: str,
    source_id: int | None,
    entry_code: str,
    amount: float,
    description: str,
    effective_at,
    created_by: int | None = None,
) -> LedgerEntry:
    reference_key = _build_reference_key(actor_type, actor_id, source_type, source_id, entry_code)
    entry = LedgerEntry.query.filter_by(reference_key=reference_key).first()
    if entry:
        return entry

    entry = LedgerEntry(
        actor_type=actor_type,
        actor_id=actor_id,
        source_type=source_type,
        source_id=source_id,
        entry_code=entry_code,
        reference_key=reference_key,
        direction=LedgerDirection.CREDIT.value,
        amount=round_amount(amount),
        currency=DEFAULT_CURRENCY,
        status=LedgerStatus.ELIGIBLE.value,
        description=description,
        effective_at=effective_at or datetime.utcnow(),
        created_by=created_by,
        updated_by=created_by,
    )
    db.session.add(entry)
    db.session.flush()
    return entry


def ensure_delivery_ledger_for_shipment(shipment_id: int) -> list[LedgerEntry]:
    shipment = Shipment.query.get(shipment_id)
    if not shipment or shipment.shipment_status != ShipmentStatus.DELIVERED.value:
        return []

    order = Order.query.get(shipment.order_id)
    if not order:
        return []

    order_items = OrderItem.query.filter_by(order_id=order.id).order_by(OrderItem.id.asc()).all()
    if not order_items:
        return []

    created_entries = []
    effective_at = shipment.delivery_time or datetime.utcnow()
    tracking_number = shipment.tracking_number or f"shipment-{shipment.id}"
    total_item_count = sum(max(int(item.quantity or 0), 0) for item in order_items) or 1

    for order_item in order_items:
        commission = ensure_commission_for_order_item(order_item)
        created_entries.append(
            ensure_system_ledger_entry(
                actor_type=LedgerActorType.VENDOR.value,
                actor_id=order_item.vendor_id,
                source_type=LedgerSourceType.ORDER_ITEM.value,
                source_id=order_item.id,
                entry_code="vendor_order_earnings",
                amount=commission.vendor_amount,
                description=f"Vendor earnings for order #{order.id} item #{order_item.id}",
                effective_at=effective_at,
            )
        )
        created_entries.append(
            ensure_system_ledger_entry(
                actor_type=LedgerActorType.PLATFORM.value,
                actor_id=None,
                source_type=LedgerSourceType.ORDER_ITEM.value,
                source_id=order_item.id,
                entry_code="platform_order_commission",
                amount=commission.platform_commission,
                description=f"Platform commission for order #{order.id} item #{order_item.id}",
                effective_at=effective_at,
            )
        )

    if shipment.assigned_delivery_boy_id:
        delivery_amount = round_amount(DELIVERY_RATE_PER_DELIVERY + (total_item_count * DELIVERY_RATE_PER_ITEM))
        created_entries.append(
            ensure_system_ledger_entry(
                actor_type=LedgerActorType.DELIVERY_BOY.value,
                actor_id=shipment.assigned_delivery_boy_id,
                source_type=LedgerSourceType.SHIPMENT.value,
                source_id=shipment.id,
                entry_code="delivery_completion_fee",
                amount=delivery_amount,
                description=f"Delivery earnings for shipment {tracking_number}",
                effective_at=effective_at,
            )
        )

    if shipment.logistics_id:
        created_entries.append(
            ensure_system_ledger_entry(
                actor_type=LedgerActorType.LOGISTICS.value,
                actor_id=shipment.logistics_id,
                source_type=LedgerSourceType.SHIPMENT.value,
                source_id=shipment.id,
                entry_code="logistics_completion_fee",
                amount=LOGISTICS_RATE_PER_SHIPMENT,
                description=f"Logistics earnings for shipment {tracking_number}",
                effective_at=effective_at,
            )
        )

    return created_entries


def get_balance_snapshot(actor_type: str, actor_id: int | None) -> dict:
    entries = apply_actor_scope(LedgerEntry.query, actor_type, actor_id).all()
    balances = {
        "pending": 0.0,
        "eligible": 0.0,
        "in_payout": 0.0,
        "settled": 0.0,
        "void": 0.0,
    }

    for entry in entries:
        bucket = entry.status
        if entry.status == LedgerStatus.ELIGIBLE.value and entry.payout_id is not None:
            bucket = "in_payout"
        balances[bucket] = balances.get(bucket, 0.0) + signed_amount(entry)

    balances["total_net"] = sum(value for key, value in balances.items() if key != "void")
    return {key: round_amount(value) for key, value in balances.items()}


def get_period_totals(actor_type: str, actor_id: int | None, start=None, end=None) -> dict:
    query = apply_actor_scope(LedgerEntry.query, actor_type, actor_id)
    if start is not None:
        query = query.filter(LedgerEntry.effective_at >= start)
    if end is not None:
        query = query.filter(LedgerEntry.effective_at < end)

    entries = query.all()
    credits = sum(round_amount(entry.amount) for entry in entries if entry.direction == LedgerDirection.CREDIT.value)
    debits = sum(round_amount(entry.amount) for entry in entries if entry.direction == LedgerDirection.DEBIT.value)
    return {
        "credits": round_amount(credits),
        "debits": round_amount(debits),
        "net": round_amount(credits - debits),
        "entries_count": len(entries),
    }


def query_actor_ledger(actor_type: str, actor_id: int | None, start=None, end=None, status: str | None = None):
    query = apply_actor_scope(LedgerEntry.query, actor_type, actor_id)
    if start is not None:
        query = query.filter(LedgerEntry.effective_at >= start)
    if end is not None:
        query = query.filter(LedgerEntry.effective_at < end)
    if status:
        normalized = status.strip().lower()
        if normalized == "in_payout":
            query = query.filter(
                LedgerEntry.status == LedgerStatus.ELIGIBLE.value,
                LedgerEntry.payout_id.isnot(None),
            )
        else:
            query = query.filter(LedgerEntry.status == normalized)

    return query.order_by(LedgerEntry.effective_at.desc(), LedgerEntry.id.desc()).all()


def build_source_context(entries: list[LedgerEntry]) -> dict[tuple[str | None, int | None], dict]:
    shipment_ids = {entry.source_id for entry in entries if entry.source_type == LedgerSourceType.SHIPMENT.value and entry.source_id}
    order_item_ids = {
        entry.source_id for entry in entries if entry.source_type == LedgerSourceType.ORDER_ITEM.value and entry.source_id
    }

    shipment_map = {}
    if shipment_ids:
        for shipment in Shipment.query.filter(Shipment.id.in_(shipment_ids)).all():
            item_count = sum(max(int(item.quantity or 0), 0) for item in shipment.order.items.all()) if shipment.order else 0
            shipment_map[shipment.id] = {
                "tracking_number": shipment.tracking_number,
                "order_id": shipment.order_id,
                "item_count": item_count,
                "delivery_time": iso_or_none(shipment.delivery_time),
            }

    order_item_map = {}
    if order_item_ids:
        for order_item in OrderItem.query.filter(OrderItem.id.in_(order_item_ids)).all():
            order_item_map[order_item.id] = {
                "order_id": order_item.order_id,
                "product_id": order_item.product_id,
                "quantity": order_item.quantity,
                "unit_price": round_amount(order_item.price),
            }

    context_map = {}
    for shipment_id, context in shipment_map.items():
        context_map[(LedgerSourceType.SHIPMENT.value, shipment_id)] = context
    for order_item_id, context in order_item_map.items():
        context_map[(LedgerSourceType.ORDER_ITEM.value, order_item_id)] = context
    return context_map


def serialize_ledger_entry(entry: LedgerEntry, source_contexts: dict | None = None, include_actor: bool = False) -> dict:
    payload = {
        "id": entry.id,
        "actor_type": entry.actor_type,
        "actor_id": entry.actor_id,
        "source_type": entry.source_type,
        "source_id": entry.source_id,
        "entry_code": entry.entry_code,
        "reference_key": entry.reference_key,
        "direction": entry.direction,
        "amount": round_amount(entry.amount),
        "currency": entry.currency,
        "status": entry.status,
        "description": entry.description,
        "effective_at": iso_or_none(entry.effective_at),
        "created_at": iso_or_none(entry.created_at),
        "payout_id": entry.payout_id,
        "payout_status": entry.payout.status if entry.payout else None,
    }
    if source_contexts:
        payload["source_context"] = source_contexts.get((entry.source_type, entry.source_id))
    if include_actor:
        payload["actor"] = resolve_actor_identity(entry.actor_type, entry.actor_id)
    return payload


def serialize_payout(payout: Payout, include_actor: bool = False) -> dict:
    payload = {
        "id": payout.id,
        "actor_type": payout.actor_type,
        "actor_id": payout.actor_id,
        "period_start": iso_or_none(payout.period_start),
        "period_end": iso_or_none(payout.period_end),
        "gross_amount": round_amount(payout.gross_amount),
        "net_amount": round_amount(payout.net_amount),
        "status": payout.status,
        "approved_at": iso_or_none(payout.approved_at),
        "paid_at": iso_or_none(payout.paid_at),
        "payment_ref": payout.payment_ref,
        "notes": payout.notes,
        "created_at": iso_or_none(payout.created_at),
        "ledger_entry_count": payout.ledger_entries.count(),
    }
    if include_actor:
        payload["actor"] = resolve_actor_identity(payout.actor_type, payout.actor_id)
    return payload


def validate_actor_reference(actor_type: str, actor_id: int | None) -> dict:
    if actor_type == LedgerActorType.PLATFORM.value:
        if actor_id is not None:
            raise ValueError("Platform actor_id must be null")
        return resolve_actor_identity(actor_type, None)
    if actor_id is None:
        raise ValueError("actor_id is required for this actor type")
    return resolve_actor_identity(actor_type, actor_id)


def create_manual_adjustment(
    *,
    actor_type: str,
    actor_id: int | None,
    direction: str,
    amount: float,
    description: str,
    created_by: int,
) -> LedgerEntry:
    validate_actor_reference(actor_type, actor_id)
    normalized_direction = (direction or "").strip().lower()
    if normalized_direction not in {LedgerDirection.CREDIT.value, LedgerDirection.DEBIT.value}:
        raise ValueError("direction must be credit or debit")
    if round_amount(amount) <= 0:
        raise ValueError("amount must be greater than 0")

    entry = LedgerEntry(
        actor_type=actor_type,
        actor_id=actor_id,
        source_type=LedgerSourceType.ADJUSTMENT.value,
        source_id=None,
        entry_code="manual_adjustment",
        reference_key=f"adjustment:{uuid4()}",
        direction=normalized_direction,
        amount=round_amount(amount),
        currency=DEFAULT_CURRENCY,
        status=LedgerStatus.ELIGIBLE.value,
        description=(description or "").strip() or "Manual finance adjustment",
        effective_at=datetime.utcnow(),
        created_by=created_by,
        updated_by=created_by,
    )
    db.session.add(entry)
    db.session.flush()
    return entry


def create_payout_batch(
    *,
    actor_type: str,
    actor_id: int | None,
    period_start,
    period_end,
    created_by: int,
    notes: str | None = None,
) -> Payout:
    validate_actor_reference(actor_type, actor_id)
    if period_start >= period_end:
        raise ValueError("period_start must be before period_end")

    query = apply_actor_scope(LedgerEntry.query, actor_type, actor_id).filter(
        LedgerEntry.status == LedgerStatus.ELIGIBLE.value,
        LedgerEntry.payout_id.is_(None),
        LedgerEntry.effective_at >= period_start,
        LedgerEntry.effective_at < period_end,
    )
    entries = query.order_by(LedgerEntry.effective_at.asc(), LedgerEntry.id.asc()).all()
    if not entries:
        raise ValueError("No eligible ledger entries found for the selected actor and period")

    gross_amount = sum(round_amount(entry.amount) for entry in entries if entry.direction == LedgerDirection.CREDIT.value)
    debit_amount = sum(round_amount(entry.amount) for entry in entries if entry.direction == LedgerDirection.DEBIT.value)
    net_amount = round_amount(gross_amount - debit_amount)
    if net_amount <= 0:
        raise ValueError("Selected ledger entries do not result in a positive payout amount")

    payout = Payout(
        actor_type=actor_type,
        actor_id=actor_id,
        period_start=period_start,
        period_end=period_end,
        gross_amount=round_amount(gross_amount),
        net_amount=net_amount,
        status=PayoutStatus.PENDING.value,
        notes=(notes or "").strip() or None,
        created_by=created_by,
        updated_by=created_by,
    )
    db.session.add(payout)
    db.session.flush()

    for entry in entries:
        entry.payout_id = payout.id
        entry.updated_by = created_by

    db.session.flush()
    return payout


def approve_payout_batch(payout: Payout, updated_by: int) -> Payout:
    if payout.status == PayoutStatus.PAID.value:
        raise ValueError("Payout is already paid")
    if payout.status == PayoutStatus.CANCELLED.value:
        raise ValueError("Cancelled payouts cannot be approved")
    payout.status = PayoutStatus.APPROVED.value
    payout.approved_at = payout.approved_at or datetime.utcnow()
    payout.updated_by = updated_by
    db.session.flush()
    return payout


def mark_payout_batch_paid(payout: Payout, *, updated_by: int, payment_ref: str | None = None) -> Payout:
    if payout.status == PayoutStatus.PAID.value:
        raise ValueError("Payout is already paid")
    if payout.status == PayoutStatus.CANCELLED.value:
        raise ValueError("Cancelled payouts cannot be marked paid")

    payout.status = PayoutStatus.PAID.value
    payout.paid_at = datetime.utcnow()
    payout.payment_ref = (payment_ref or "").strip() or payout.payment_ref
    payout.updated_by = updated_by

    for entry in payout.ledger_entries.all():
        if entry.status == LedgerStatus.ELIGIBLE.value:
            entry.status = LedgerStatus.SETTLED.value
            entry.updated_by = updated_by

    db.session.flush()
    return payout


def list_actor_balances(actor_type: str) -> list[dict]:
    if actor_type == LedgerActorType.VENDOR.value:
        profiles = VendorProfile.query.join(User).order_by(VendorProfile.store_name.asc(), User.name.asc()).all()
    elif actor_type == LedgerActorType.DELIVERY_BOY.value:
        profiles = DeliveryProfile.query.join(User).order_by(User.name.asc()).all()
    elif actor_type == LedgerActorType.LOGISTICS.value:
        profiles = LogisticsProfile.query.join(User).order_by(User.name.asc()).all()
    else:
        raise ValueError("role must be vendor, delivery_boy, or logistics")

    entries = LedgerEntry.query.filter(LedgerEntry.actor_type == actor_type).all()
    payouts = Payout.query.filter(Payout.actor_type == actor_type).order_by(Payout.created_at.desc()).all()

    balance_map = defaultdict(
        lambda: {
            "pending": 0.0,
            "eligible": 0.0,
            "in_payout": 0.0,
            "settled": 0.0,
        }
    )
    for entry in entries:
        if entry.actor_id is None:
            continue
        bucket = "in_payout" if entry.status == LedgerStatus.ELIGIBLE.value and entry.payout_id is not None else entry.status
        if bucket not in balance_map[entry.actor_id]:
            continue
        balance_map[entry.actor_id][bucket] += signed_amount(entry)

    payout_map = defaultdict(list)
    for payout in payouts:
        if payout.actor_id is not None:
            payout_map[payout.actor_id].append(payout)

    rows = []
    for profile in profiles:
        user = profile.user
        actor_id = profile.id
        if actor_type == LedgerActorType.VENDOR.value:
            name = profile.store_name or (user.name if user else f"Vendor #{actor_id}")
            secondary = user.name if user else None
        else:
            name = user.name if user else f"Actor #{actor_id}"
            secondary = profile.phone if actor_type == LedgerActorType.DELIVERY_BOY.value else profile.service_area

        actor_payouts = payout_map.get(actor_id, [])
        balances = balance_map[actor_id]
        rows.append(
            {
                "actor_type": actor_type,
                "actor_id": actor_id,
                "user_id": profile.user_id,
                "name": name,
                "email": user.email if user else None,
                "secondary_label": secondary,
                "balances": {key: round_amount(value) for key, value in balances.items()},
                "total_net": round_amount(sum(balances.values())),
                "payouts_count": len(actor_payouts),
                "last_payout_at": iso_or_none(actor_payouts[0].paid_at or actor_payouts[0].created_at) if actor_payouts else None,
            }
        )

    return rows


def build_admin_overview(start=None, end=None) -> dict:
    actor_types = [
        LedgerActorType.VENDOR.value,
        LedgerActorType.DELIVERY_BOY.value,
        LedgerActorType.LOGISTICS.value,
        LedgerActorType.PLATFORM.value,
    ]

    current_entries = LedgerEntry.query.all()
    period_query = LedgerEntry.query
    if start is not None:
        period_query = period_query.filter(LedgerEntry.effective_at >= start)
    if end is not None:
        period_query = period_query.filter(LedgerEntry.effective_at < end)
    period_entries = period_query.all()
    payouts = Payout.query.all()

    actor_counts = {
        LedgerActorType.VENDOR.value: VendorProfile.query.count(),
        LedgerActorType.DELIVERY_BOY.value: DeliveryProfile.query.count(),
        LedgerActorType.LOGISTICS.value: LogisticsProfile.query.count(),
        LedgerActorType.PLATFORM.value: 1,
    }

    current_balances = defaultdict(
        lambda: {
            "eligible": 0.0,
            "in_payout": 0.0,
            "settled": 0.0,
            "pending": 0.0,
        }
    )
    for entry in current_entries:
        bucket = "in_payout" if entry.status == LedgerStatus.ELIGIBLE.value and entry.payout_id is not None else entry.status
        if bucket not in current_balances[entry.actor_type]:
            continue
        current_balances[entry.actor_type][bucket] += signed_amount(entry)

    period_balances = defaultdict(float)
    for entry in period_entries:
        period_balances[entry.actor_type] += signed_amount(entry)

    payout_counts = defaultdict(lambda: defaultdict(int))
    for payout in payouts:
        payout_counts[payout.actor_type][payout.status] += 1

    overview = []
    for actor_type in actor_types:
        balances = current_balances[actor_type]
        overview.append(
            {
                "actor_type": actor_type,
                "actor_count": actor_counts.get(actor_type, 0),
                "period_net": round_amount(period_balances[actor_type]),
                "eligible_balance": round_amount(balances["eligible"]),
                "in_payout_amount": round_amount(balances["in_payout"]),
                "settled_amount": round_amount(balances["settled"]),
                "pending_amount": round_amount(balances["pending"]),
                "payout_counts": {
                    "pending": int(payout_counts[actor_type][PayoutStatus.PENDING.value]),
                    "approved": int(payout_counts[actor_type][PayoutStatus.APPROVED.value]),
                    "paid": int(payout_counts[actor_type][PayoutStatus.PAID.value]),
                    "failed": int(payout_counts[actor_type][PayoutStatus.FAILED.value]),
                    "cancelled": int(payout_counts[actor_type][PayoutStatus.CANCELLED.value]),
                },
            }
        )

    recent_payouts = (
        Payout.query.order_by(Payout.created_at.desc()).limit(12).all()
    )
    return {
        "overview": overview,
        "recent_payouts": [serialize_payout(payout, include_actor=True) for payout in recent_payouts],
    }


def list_admin_payouts(actor_type: str | None = None, status: str | None = None) -> list[dict]:
    query = Payout.query
    if actor_type:
        query = query.filter(Payout.actor_type == actor_type)
    if status:
        query = query.filter(Payout.status == status)
    payouts = query.order_by(Payout.created_at.desc(), Payout.id.desc()).all()
    return [serialize_payout(payout, include_actor=True) for payout in payouts]


def list_adjustments(actor_type: str | None = None, actor_id: int | None = None) -> list[dict]:
    query = LedgerEntry.query.filter(LedgerEntry.source_type == LedgerSourceType.ADJUSTMENT.value)
    if actor_type:
        query = query.filter(LedgerEntry.actor_type == actor_type)
    if actor_type and actor_id is None and actor_type == LedgerActorType.PLATFORM.value:
        query = query.filter(LedgerEntry.actor_id.is_(None))
    elif actor_id is not None:
        query = query.filter(LedgerEntry.actor_id == actor_id)
    entries = query.order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc()).all()
    return [serialize_ledger_entry(entry, include_actor=True) for entry in entries]
