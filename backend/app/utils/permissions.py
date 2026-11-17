
from bson import ObjectId
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from app import extensions


def get_current_user():
    verify_jwt_in_request()

    user_id = get_jwt_identity()

    try:
        user = extensions.db.users.find_one({"_id": ObjectId(str(user_id))})
    except Exception:
        return None

    if not user or not user.get("is_active", False):
        return None

    return user


def get_optional_user():
    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if not user_id:
            return None
        user = extensions.db.users.find_one({"_id": ObjectId(str(user_id))})
        if not user or not user.get("is_active", False):
            return None
        return user
    except Exception:
        return None


def is_active_user(user):
    return bool(user and user.get("is_active", False))


def is_super_admin(user):
    return bool(user and user.get("role") == "super_admin")


def is_division_admin(user):
    return bool(user and user.get("role") == "division_admin")


def belongs_to_division(user, division):
    return bool(
        user
        and user.get("division")
        and user.get("division") == division
    )


def has_approved_cross_division_access(user, document):
    if not user or not document:
        return False

    try:
        request = extensions.db.access_requests.find_one({
            "user_id": user["_id"],
            "document_id": document["_id"],
            "status": "approved"
        })

        return request is not None

    except Exception:
        return False


def can_access_document(user, document):
    if not is_active_user(user) or not document:
        return False

    if is_super_admin(user):
        return True

    if belongs_to_division(user, document.get("division")):
        return True

    return has_approved_cross_division_access(user, document)


def can_manage_user(admin, target):
    if not is_active_user(admin) or not target:
        return False

    if is_super_admin(admin):
        return True

    if is_division_admin(admin):
        return belongs_to_division(admin, target.get("division"))

    return False


def user_to_json(user):
    return {
        "id": str(user["_id"]),
        "name": user.get("name"),
        "email": user.get("email"),
        "division": user.get("division"),
        "role": user.get("role", "user"),
        "is_active": user.get("is_active", False)
    }
