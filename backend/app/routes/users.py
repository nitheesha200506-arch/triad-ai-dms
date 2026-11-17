
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app import extensions

class _DBProxy:
    def __getattr__(self, name):
        return getattr(extensions.db, name)

db = _DBProxy()

from app.utils.permissions import (
    get_current_user,
    is_super_admin,
    is_division_admin,
    can_manage_user,
    user_to_json
)

users = Blueprint("users", __name__)

ALLOWED_ROLES = [
    "user",
    "division_admin",
    "super_admin"
]


def get_object_id(user_id):

    if not ObjectId.is_valid(user_id):
        return None

    return ObjectId(user_id)


# GET ALL USERS
@users.route("/users", methods=["GET"])
@jwt_required()
def get_users():

    current_user = get_current_user()

    if not current_user:
        return jsonify({
            "message": "User not found or inactive"
        }), 401

    if is_super_admin(current_user):
        query = {}

    elif is_division_admin(current_user):
        query = {
            "division": current_user["division"]
        }

    else:
        return jsonify({
            "message": "Permission denied"
        }), 403

    result = db.users.find(query)

    user_list = [
        user_to_json(user)
        for user in result
    ]

    return jsonify({
        "message": "Users retrieved successfully",
        "users": user_list
    }), 200


# GET ONE USER
@users.route("/users/<user_id>", methods=["GET"])
@jwt_required()
def get_user(user_id):

    current_user = get_current_user()

    if not current_user:
        return jsonify({
            "message": "User not found or inactive"
        }), 401

    object_id = get_object_id(user_id)

    if object_id is None:
        return jsonify({
            "message": "Invalid user ID"
        }), 400

    target = db.users.find_one({
        "_id": object_id
    })

    if not target:
        return jsonify({
            "message": "User not found"
        }), 404

    if not (
        str(current_user["_id"]) == str(target["_id"])
        or can_manage_user(current_user, target)
    ):
        return jsonify({
            "message": "Permission denied"
        }), 403

    return jsonify({
        "message": "User retrieved successfully",
        "user": user_to_json(target)
    }), 200


# UPDATE USER
@users.route("/users/<user_id>", methods=["PUT"])
@jwt_required()
def update_user(user_id):

    current_user = get_current_user()

    if not current_user:
        return jsonify({
            "message": "User not found or inactive"
        }), 401

    object_id = get_object_id(user_id)

    if object_id is None:
        return jsonify({
            "message": "Invalid user ID"
        }), 400

    target = db.users.find_one({
        "_id": object_id
    })

    if not target:
        return jsonify({
            "message": "User not found"
        }), 404

    if not can_manage_user(current_user, target):
        return jsonify({
            "message": "Permission denied"
        }), 403

    if str(current_user["_id"]) == str(target["_id"]):
        return jsonify({
            "message": "You cannot manage your own account here"
        }), 403

    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not data:
        return jsonify({
            "message": "Provide valid update data"
        }), 400

    allowed_fields = ["name", "email"]

    if is_super_admin(current_user):
        allowed_fields.extend([
            "division",
            "role"
        ])

    updates = {}

    for field in allowed_fields:

        if field in data:

            value = data[field]

            if not isinstance(value, str) or not value.strip():
                return jsonify({
                    "message": field + " must be a non-empty string"
                }), 400

            value = value.strip()

            if field == "email":
                value = value.lower()

            if field == "role" and value not in ALLOWED_ROLES:
                return jsonify({
                    "message": "Invalid role"
                }), 400

            if field == "division":
                division = db.divisions.find_one({
                    "name": value,
                    "active": True
                })

                if not division:
                    return jsonify({
                        "message": "Invalid or inactive division"
                    }), 400

            updates[field] = value

    if not updates:
        return jsonify({
            "message": "No permitted fields to update"
        }), 400

    try:
        db.users.update_one(
            {"_id": object_id},
            {"$set": updates}
        )

    except DuplicateKeyError:
        return jsonify({
            "message": "Email already registered"
        }), 409

    updated_user = db.users.find_one({
        "_id": object_id
    })

    return jsonify({
        "message": "User updated successfully",
        "user": user_to_json(updated_user)
    }), 200


# DEACTIVATE USER
@users.route("/users/<user_id>", methods=["DELETE"])
@jwt_required()
def deactivate_user(user_id):

    current_user = get_current_user()

    if not current_user:
        return jsonify({
            "message": "User not found or inactive"
        }), 401

    object_id = get_object_id(user_id)

    if object_id is None:
        return jsonify({
            "message": "Invalid user ID"
        }), 400

    target = db.users.find_one({
        "_id": object_id
    })

    if not target:
        return jsonify({
            "message": "User not found"
        }), 404

    if not can_manage_user(current_user, target):
        return jsonify({
            "message": "Permission denied"
        }), 403

    if str(current_user["_id"]) == str(target["_id"]):
        return jsonify({
            "message": "You cannot deactivate yourself"
        }), 403

    if target.get("role") == "super_admin" and not is_super_admin(current_user):
        return jsonify({
            "message": "Only a super admin can deactivate a super admin"
        }), 403

    db.users.update_one(
        {"_id": object_id},
        {
            "$set": {
                "is_active": False
            }
        }
    )

    return jsonify({
        "message": "User deactivated successfully"
    }), 200


# GET DIVISIONS
@users.route("/divisions", methods=["GET"])
@jwt_required()
def get_divisions():

    current_user = get_current_user()

    if not current_user:
        return jsonify({
            "message": "User not found or inactive"
        }), 401

    divisions = list(
        db.divisions.find(
            {"active": True},
            {"_id": 0, "name": 1}
        ).sort("name", 1)
    )

    return jsonify({
        "message": "Divisions retrieved successfully",
        "divisions": divisions
    }), 200
