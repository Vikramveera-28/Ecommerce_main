from functools import wraps

from flask import jsonify
from bson import ObjectId
from flask import current_app
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.models import AccountStatus, Role, User


def _lookup_user(user_id):
    if current_app.config.get("USE_MONGO_ONLY", False):
        mongo_db = current_app.extensions.get("mongo_db")
        if mongo_db is None:
            return None
        try:
            mongo_id = ObjectId(str(user_id))
        except Exception:
            return None
        return mongo_db["users"].find_one({"_id": mongo_id})
    return User.query.get(int(user_id))


def _get_user_role(user_obj):
    if isinstance(user_obj, dict):
        return user_obj.get("role")
    return user_obj.role


def _get_user_status(user_obj):
    if isinstance(user_obj, dict):
        return user_obj.get("status")
    return user_obj.status


def role_required(*roles: Role):
    role_values = {r.value if isinstance(r, Role) else str(r) for r in roles}

    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            user_id = get_jwt_identity()
            user = _lookup_user(user_id)
            if not user:
                return jsonify({"error": "User not found"}), 404
            if _get_user_status(user) != AccountStatus.ACTIVE.value:
                return jsonify({"error": "Account is not active"}), 403
            if _get_user_role(user) not in role_values:
                return jsonify({"error": "Insufficient permissions"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def current_user():
    user_id = get_jwt_identity()
    if not user_id:
        return None
    return _lookup_user(user_id)
