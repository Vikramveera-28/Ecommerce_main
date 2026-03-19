from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from app.common.authz import current_user, role_required
from app.extensions import db
from app.finance.service import (
    DELIVERY_RATE_PER_DELIVERY,
    DELIVERY_RATE_PER_ITEM,
    LOGISTICS_RATE_PER_SHIPMENT,
    approve_payout_batch,
    build_admin_overview,
    build_source_context,
    create_manual_adjustment,
    create_payout_batch,
    get_balance_snapshot,
    get_period_totals,
    list_actor_balances,
    list_adjustments,
    list_admin_payouts,
    mark_payout_batch_paid,
    query_actor_ledger,
    resolve_finance_actor,
    round_amount,
    serialize_ledger_entry,
    serialize_payout,
    validate_actor_reference,
)
from app.models import LedgerActorType, Payout, Role


finance_bp = Blueprint("finance", __name__)

SELF_RANGE_TO_DAYS = {
    "7d": 7,
    "30d": 30,
    "all": None,
}

ADMIN_RANGE_TO_DAYS = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "all": None,
}


def _normalize_actor_type(value):
    normalized = (value or "").strip().lower()
    if not normalized:
        return None
    allowed = {
        LedgerActorType.VENDOR.value,
        LedgerActorType.DELIVERY_BOY.value,
        LedgerActorType.LOGISTICS.value,
        LedgerActorType.PLATFORM.value,
    }
    if normalized not in allowed:
        raise ValueError("actor_type must be vendor, delivery_boy, logistics, or platform")
    return normalized


def _resolve_range_window(mapping):
    range_key = (request.args.get("range") or "30d").strip().lower()
    if range_key not in mapping:
        raise ValueError(f"range must be one of {', '.join(mapping.keys())}")

    days = mapping[range_key]
    end = datetime.utcnow()
    start = end - timedelta(days=days) if days is not None else None
    return range_key, start, end


def _parse_period_boundaries(payload):
    raw_start = str(payload.get("period_start") or "").strip()
    raw_end = str(payload.get("period_end") or "").strip()
    if not raw_start or not raw_end:
        raise ValueError("period_start and period_end are required")

    try:
        start = datetime.fromisoformat(raw_start)
    except ValueError as exc:
        raise ValueError("period_start must be an ISO date or datetime") from exc

    try:
        end = datetime.fromisoformat(raw_end)
    except ValueError as exc:
        raise ValueError("period_end must be an ISO date or datetime") from exc

    if len(raw_end) == 10:
        end = end + timedelta(days=1)
    return start, end


def _admin_actor_payload():
    data = request.get_json(silent=True) or {}
    actor_type = _normalize_actor_type(data.get("actor_type") or data.get("role"))
    if not actor_type:
        raise ValueError("actor_type is required")

    actor_id = data.get("actor_id")
    if actor_type == LedgerActorType.PLATFORM.value:
        actor_id = None
    elif actor_id is None:
        raise ValueError("actor_id is required")
    else:
        try:
            actor_id = int(actor_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("actor_id must be an integer") from exc

    validate_actor_reference(actor_type, actor_id)
    return data, actor_type, actor_id


@finance_bp.get("/me/summary")
@role_required(Role.VENDOR, Role.DELIVERY_BOY, Role.LOGISTICS, Role.ADMIN)
def finance_me_summary():
    user = current_user()
    try:
        actor = resolve_finance_actor(user)
        range_key, start, end = _resolve_range_window(SELF_RANGE_TO_DAYS)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    balances = get_balance_snapshot(actor["actor_type"], actor["actor_id"])
    period_totals = get_period_totals(actor["actor_type"], actor["actor_id"], start=start, end=end)
    last_payout = (
        Payout.query.filter_by(actor_type=actor["actor_type"], actor_id=actor["actor_id"])
        .order_by(Payout.created_at.desc())
        .first()
    )

    payload = {
        "actor": actor,
        "currency": "INR",
        "range": range_key,
        "balances": balances,
        "period": period_totals,
        "last_payout": serialize_payout(last_payout) if last_payout else None,
    }
    if actor["actor_type"] == LedgerActorType.DELIVERY_BOY.value:
        payload["compensation"] = {
            "per_delivery": round_amount(DELIVERY_RATE_PER_DELIVERY),
            "per_item": round_amount(DELIVERY_RATE_PER_ITEM),
        }
    if actor["actor_type"] == LedgerActorType.LOGISTICS.value:
        payload["compensation"] = {
            "per_completed_shipment": round_amount(LOGISTICS_RATE_PER_SHIPMENT),
        }
    return jsonify(payload)


@finance_bp.get("/me/ledger")
@role_required(Role.VENDOR, Role.DELIVERY_BOY, Role.LOGISTICS, Role.ADMIN)
def finance_me_ledger():
    user = current_user()
    try:
        actor = resolve_finance_actor(user)
        _, start, end = _resolve_range_window(SELF_RANGE_TO_DAYS)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    status = (request.args.get("status") or "").strip().lower() or None
    entries = query_actor_ledger(actor["actor_type"], actor["actor_id"], start=start, end=end, status=status)
    source_contexts = build_source_context(entries)
    return jsonify([serialize_ledger_entry(entry, source_contexts=source_contexts) for entry in entries])


@finance_bp.get("/me/payouts")
@role_required(Role.VENDOR, Role.DELIVERY_BOY, Role.LOGISTICS, Role.ADMIN)
def finance_me_payouts():
    user = current_user()
    try:
        actor = resolve_finance_actor(user)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    payouts = (
        Payout.query.filter_by(actor_type=actor["actor_type"], actor_id=actor["actor_id"])
        .order_by(Payout.created_at.desc(), Payout.id.desc())
        .all()
    )
    return jsonify([serialize_payout(payout) for payout in payouts])


@finance_bp.get("/admin/overview")
@role_required(Role.ADMIN)
def finance_admin_overview():
    try:
        range_key, start, end = _resolve_range_window(ADMIN_RANGE_TO_DAYS)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    payload = build_admin_overview(start=start, end=end)
    payload["range"] = range_key
    return jsonify(payload)


@finance_bp.get("/admin/actors")
@role_required(Role.ADMIN)
def finance_admin_actors():
    actor_type = _normalize_actor_type(request.args.get("role") or request.args.get("actor_type"))
    if actor_type not in {
        LedgerActorType.VENDOR.value,
        LedgerActorType.DELIVERY_BOY.value,
        LedgerActorType.LOGISTICS.value,
    }:
        return jsonify({"error": "role must be vendor, delivery_boy, or logistics"}), 400

    try:
        rows = list_actor_balances(actor_type)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(rows)


@finance_bp.get("/admin/payouts")
@role_required(Role.ADMIN)
def finance_admin_list_payouts():
    try:
        actor_type = _normalize_actor_type(request.args.get("role") or request.args.get("actor_type"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    status = (request.args.get("status") or "").strip().lower() or None
    return jsonify(list_admin_payouts(actor_type=actor_type, status=status))


@finance_bp.post("/admin/payouts")
@role_required(Role.ADMIN)
def finance_admin_create_payout():
    user = current_user()
    try:
        data, actor_type, actor_id = _admin_actor_payload()
        period_start, period_end = _parse_period_boundaries(data)
        payout = create_payout_batch(
            actor_type=actor_type,
            actor_id=actor_id,
            period_start=period_start,
            period_end=period_end,
            created_by=user.id,
            notes=data.get("notes"),
        )
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400

    return jsonify(serialize_payout(payout, include_actor=True)), 201


@finance_bp.patch("/admin/payouts/<int:payout_id>/approve")
@role_required(Role.ADMIN)
def finance_admin_approve_payout(payout_id: int):
    user = current_user()
    payout = Payout.query.get(payout_id)
    if not payout:
        return jsonify({"error": "Payout not found"}), 404

    try:
        approve_payout_batch(payout, updated_by=user.id)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400

    return jsonify(serialize_payout(payout, include_actor=True))


@finance_bp.patch("/admin/payouts/<int:payout_id>/mark-paid")
@role_required(Role.ADMIN)
def finance_admin_mark_payout_paid(payout_id: int):
    user = current_user()
    payout = Payout.query.get(payout_id)
    if not payout:
        return jsonify({"error": "Payout not found"}), 404

    data = request.get_json(silent=True) or {}
    try:
        mark_payout_batch_paid(payout, updated_by=user.id, payment_ref=data.get("payment_ref"))
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400

    return jsonify(serialize_payout(payout, include_actor=True))


@finance_bp.get("/admin/adjustments")
@role_required(Role.ADMIN)
def finance_admin_list_adjustments():
    try:
        actor_type = _normalize_actor_type(request.args.get("role") or request.args.get("actor_type"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    actor_id = request.args.get("actor_id")
    if actor_id is not None:
        try:
            actor_id = int(actor_id)
        except (TypeError, ValueError):
            return jsonify({"error": "actor_id must be an integer"}), 400

    return jsonify(list_adjustments(actor_type=actor_type, actor_id=actor_id))


@finance_bp.post("/admin/adjustments")
@role_required(Role.ADMIN)
def finance_admin_create_adjustment():
    user = current_user()
    try:
        data, actor_type, actor_id = _admin_actor_payload()
        adjustment = create_manual_adjustment(
            actor_type=actor_type,
            actor_id=actor_id,
            direction=data.get("direction"),
            amount=data.get("amount"),
            description=data.get("description"),
            created_by=user.id,
        )
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400

    return jsonify(serialize_ledger_entry(adjustment, include_actor=True)), 201
