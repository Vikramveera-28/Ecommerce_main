from datetime import datetime, timezone

from bson import ObjectId
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, limiter
from app.common.utils import slugify
from app.models import (
    AccountStatus,
    CustomerProfile,
    DeliveryProfile,
    LogisticsProfile,
    RevokedToken,
    Role,
    User,
    VendorKycStatus,
    VendorProfile,
)


auth_bp = Blueprint("auth", __name__)


def _mongo_enabled() -> bool:
    return bool(current_app.config.get("USE_MONGO_ONLY", False))


def _mongo_db():
    return current_app.extensions.get("mongo_db")


def _mongo_users():
    db_obj = _mongo_db()
    return db_obj["users"] if db_obj is not None else None


def _mongo_revoked_tokens():
    db_obj = _mongo_db()
    return db_obj["revoked_tokens"] if db_obj is not None else None


def _serialize_mongo_user(user_doc):
    return {
        "id": str(user_doc["_id"]),
        "name": user_doc.get("name", ""),
        "email": user_doc.get("email", ""),
        "role": user_doc.get("role", Role.CUSTOMER.value),
        "status": user_doc.get("status", AccountStatus.PENDING.value),
    }


@auth_bp.post("/register")
@limiter.limit("10 per minute")
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip() or None
    password = data.get("password") or ""
    role = (data.get("role") or Role.CUSTOMER.value).lower()

    if not name or not email or not password:
        return jsonify({"error": "name, email, password are required"}), 400
    if role not in {r.value for r in Role}:
        return jsonify({"error": "Invalid role"}), 400
    if role == Role.ADMIN.value:
        return jsonify({"error": "Admin self-registration is not allowed"}), 403
    if _mongo_enabled():
        users = _mongo_users()
        if users is None:
            return jsonify({"error": "MongoDB is not configured"}), 500
        if users.find_one({"email": email}):
            return jsonify({"error": "Email already registered"}), 409

        status = AccountStatus.ACTIVE.value if role == Role.CUSTOMER.value else AccountStatus.PENDING.value
        now = datetime.now(timezone.utc)
        result = users.insert_one(
            {
                "name": name,
                "email": email,
                "phone": phone,
                "password_hash": generate_password_hash(password),
                "role": role,
                "status": status,
                "created_at": now,
                "updated_at": now,
            }
        )
        return jsonify({"id": str(result.inserted_id), "email": email, "role": role, "status": status}), 201

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    user = User(name=name, email=email, phone=phone, role=role)
    user.set_password(password)

    if role == Role.CUSTOMER.value:
        user.status = AccountStatus.ACTIVE.value
    else:
        user.status = AccountStatus.PENDING.value

    db.session.add(user)
    db.session.flush()

    if role == Role.CUSTOMER.value:
        db.session.add(CustomerProfile(user_id=user.id))
    elif role == Role.VENDOR.value:
        db.session.add(
            VendorProfile(
                user_id=user.id,
                store_name=f"{name} Store",
                store_slug=slugify(f"{name}-store-{user.id}"),
                kyc_status=VendorKycStatus.PENDING.value,
            )
        )
    elif role == Role.LOGISTICS.value:
        db.session.add(LogisticsProfile(user_id=user.id, status=AccountStatus.ACTIVE.value))
    elif role == Role.DELIVERY_BOY.value:
        db.session.add(DeliveryProfile(user_id=user.id, phone=phone, is_active=True))

    db.session.commit()

    return jsonify({"id": user.id, "email": user.email, "role": user.role, "status": user.status}), 201


@auth_bp.post("/login")
@limiter.limit("20 per minute")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if _mongo_enabled():
        users = _mongo_users()
        if users is None:
            return jsonify({"error": "MongoDB is not configured"}), 500

        user_doc = users.find_one({"email": email})
        if not user_doc or not check_password_hash(user_doc.get("password_hash", ""), password):
            return jsonify({"error": "Invalid credentials"}), 401
        if user_doc.get("status") != AccountStatus.ACTIVE.value:
            return jsonify({"error": "Account is not active"}), 403

        additional_claims = {
            "role": user_doc.get("role", Role.CUSTOMER.value),
            "status": user_doc.get("status", AccountStatus.PENDING.value),
        }
        access_token = create_access_token(identity=str(user_doc["_id"]), additional_claims=additional_claims)
        refresh_token = create_refresh_token(identity=str(user_doc["_id"]), additional_claims=additional_claims)
        return jsonify(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": _serialize_mongo_user(user_doc),
            }
        )

    try:
        user = User.query.filter_by(email=email).first()
    except SQLAlchemyError:
        return jsonify({"error": "Database unavailable. Please try again."}), 503
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401
    if user.status != AccountStatus.ACTIVE.value:
        return jsonify({"error": "Account is not active"}), 403

    additional_claims = {"role": user.role, "status": user.status}
    access_token = create_access_token(identity=str(user.id), additional_claims=additional_claims)
    refresh_token = create_refresh_token(identity=str(user.id), additional_claims=additional_claims)

    return jsonify(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "status": user.status,
            },
        }
    )


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    if _mongo_enabled():
        users = _mongo_users()
        if users is None:
            return jsonify({"error": "MongoDB is not configured"}), 500
        try:
            mongo_id = ObjectId(user_id)
        except Exception:
            return jsonify({"error": "User not allowed"}), 403
        user_doc = users.find_one({"_id": mongo_id})
        if not user_doc or user_doc.get("status") != AccountStatus.ACTIVE.value:
            return jsonify({"error": "User not allowed"}), 403
        claims = {
            "role": user_doc.get("role", Role.CUSTOMER.value),
            "status": user_doc.get("status", AccountStatus.PENDING.value),
        }
        new_access = create_access_token(identity=str(user_doc["_id"]), additional_claims=claims)
        return jsonify({"access_token": new_access})

    user = User.query.get(int(user_id))
    if not user or user.status != AccountStatus.ACTIVE.value:
        return jsonify({"error": "User not allowed"}), 403

    claims = {"role": user.role, "status": user.status}
    new_access = create_access_token(identity=str(user.id), additional_claims=claims)
    return jsonify({"access_token": new_access})


@auth_bp.post("/logout")
@jwt_required(verify_type=False)
def logout():
    token = get_jwt()
    jti = token.get("jti")
    token_type = token.get("type", "access")
    exp = token.get("exp")
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)

    if _mongo_enabled():
        revoked_tokens = _mongo_revoked_tokens()
        if revoked_tokens is None:
            return jsonify({"error": "MongoDB is not configured"}), 500
        revoked_tokens.insert_one(
            {
                "jti": jti,
                "token_type": token_type,
                "expires_at": expires_at,
                "created_at": datetime.now(timezone.utc),
            }
        )
    else:
        revoked = RevokedToken(jti=jti, token_type=token_type, expires_at=expires_at)
        db.session.add(revoked)
        db.session.commit()

    return jsonify({"message": "Logged out"})
