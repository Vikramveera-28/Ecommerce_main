from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.models import AccountStatus, Role, User


def role_required(*roles: Role):
    role_values = {r.value if isinstance(r, Role) else str(r) for r in roles}

    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            user_id = get_jwt_identity()
            user = User.query.get(int(user_id))
            if not user:
                return jsonify({"error": "User not found"}), 404
            if user.status != AccountStatus.ACTIVE.value:
                return jsonify({"error": "Account is not active"}), 403
            if user.role not in role_values:
                return jsonify({"error": "Insufficient permissions"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def current_user():
    user_id = get_jwt_identity()
    if not user_id:
        return None
    return User.query.get(int(user_id))
