
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
from datetime import datetime, timezone

from app import extensions

metadata = Blueprint("metadata", __name__)

ALLOWED_TYPES = ["text", "number", "date", "dropdown"]


def get_admin():
    user_id = get_jwt_identity()

    if not ObjectId.is_valid(user_id):
        return None

    user = extensions.db.users.find_one({"_id": ObjectId(user_id)})

    if not user or not user.get("is_active", True):
        return None

    if user.get("role") not in ["super_admin", "division_admin"]:
        return None

    return user


def serialize_field(field):
    return {
        "id": str(field["_id"]),
        "field_name": field["field_name"],
        "field_type": field["field_type"],
        "options": field.get("options", []),
        "required": field.get("required", False),
        "active": field.get("active", True),
        "created_at": field.get("created_at").isoformat()
        if field.get("created_at") else None,
        "updated_at": field.get("updated_at").isoformat()
        if field.get("updated_at") else None
    }


def validate_field_data(data):
    if not isinstance(data, dict):
        return "Request body must be a JSON object"

    name = data.get("field_name")
    field_type = data.get("field_type")

    if not isinstance(name, str) or not name.strip():
        return "field_name is required"

    if len(name.strip()) > 100:
        return "field_name must not exceed 100 characters"

    if field_type not in ALLOWED_TYPES:
        return "field_type must be text, number, date or dropdown"

    options = data.get("options", [])

    if field_type == "dropdown":
        if not isinstance(options, list) or not options:
            return "Dropdown fields must have at least one option"

        if not all(isinstance(option, str) and option.strip()
                   for option in options):
            return "All dropdown options must be non-empty strings"

        if len(set(option.strip().casefold() for option in options)) != len(options):
            return "Dropdown options must be unique"

    elif options not in (None, []):
        return "Options are only allowed for dropdown fields"

    if "required" in data and not isinstance(data["required"], bool):
        return "required must be true or false"

    return None


@metadata.route("", methods=["POST"])
@jwt_required()
def create_metadata():

    admin = get_admin()

    if not admin:
        return jsonify({"message": "Administrator access required"}), 403

    data = request.get_json(silent=True)

    error = validate_field_data(data)

    if error:
        return jsonify({"message": error}), 400

    field_name = data["field_name"].strip()

    existing = extensions.db.metadata_fields.find_one({
        "field_name": {
            "$regex": "^" + __import__("re").escape(field_name) + "$",
            "$options": "i"
        }
    })

    if existing:
        return jsonify({"message": "Metadata field already exists"}), 409

    field = {
        "field_name": field_name,
        "field_type": data["field_type"],
        "options": [x.strip() for x in data.get("options", [])],
        "required": data.get("required", False),
        "active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = extensions.db.metadata_fields.insert_one(field)

    field["_id"] = result.inserted_id

    return jsonify({
        "message": "Metadata field created successfully",
        "field": serialize_field(field)
    }), 201


@metadata.route("", methods=["GET"])
@jwt_required()
def get_metadata():

    admin = get_admin()

    if not admin:
        return jsonify({"message": "Administrator access required"}), 403

    fields = list(
        extensions.db.metadata_fields.find().sort("created_at", -1)
    )

    return jsonify({
        "count": len(fields),
        "metadata_fields": [serialize_field(f) for f in fields]
    }), 200


@metadata.route("/<id>", methods=["PUT"])
@jwt_required()
def update_metadata(id):

    admin = get_admin()

    if not admin:
        return jsonify({"message": "Administrator access required"}), 403

    if not ObjectId.is_valid(id):
        return jsonify({"message": "Invalid metadata ID"}), 400

    existing = extensions.db.metadata_fields.find_one({"_id": ObjectId(id)})

    if not existing:
        return jsonify({"message": "Metadata field not found"}), 404

    data = request.get_json(silent=True)

    error = validate_field_data(data)

    if error:
        return jsonify({"message": error}), 400

    field_name = data["field_name"].strip()

    duplicate = extensions.db.metadata_fields.find_one({
        "_id": {"$ne": ObjectId(id)},
        "field_name": {
            "$regex": "^" + __import__("re").escape(field_name) + "$",
            "$options": "i"
        }
    })

    if duplicate:
        return jsonify({"message": "Metadata field already exists"}), 409

    update_data = {
        "field_name": field_name,
        "field_type": data["field_type"],
        "options": [x.strip() for x in data.get("options", [])],
        "required": data.get("required", False),
        "updated_at": datetime.now(timezone.utc)
    }

    extensions.db.metadata_fields.update_one(
        {"_id": ObjectId(id)},
        {"$set": update_data}
    )

    updated = extensions.db.metadata_fields.find_one({"_id": ObjectId(id)})

    return jsonify({
        "message": "Metadata field updated successfully",
        "field": serialize_field(updated)
    }), 200


@metadata.route("/<id>", methods=["DELETE"])
@jwt_required()
def deactivate_metadata(id):

    admin = get_admin()

    if not admin:
        return jsonify({"message": "Administrator access required"}), 403

    if not ObjectId.is_valid(id):
        return jsonify({"message": "Invalid metadata ID"}), 400

    existing = extensions.db.metadata_fields.find_one({"_id": ObjectId(id)})

    if not existing:
        return jsonify({"message": "Metadata field not found"}), 404

    extensions.db.metadata_fields.update_one(
        {"_id": ObjectId(id)},
        {
            "$set": {
                "active": False,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )

    return jsonify({
        "message": "Metadata field deactivated successfully"
    }), 200



@metadata.route("/active", methods=["GET"])
@jwt_required()
def get_active_metadata():

    admin = get_admin()

    if not admin:
        return jsonify({"message": "Administrator access required"}), 403

    fields = list(
        extensions.db.metadata_fields.find(
            {"active": True}
        ).sort("created_at", -1)
    )

    return jsonify({
        "count": len(fields),
        "metadata_fields": [serialize_field(f) for f in fields]
    }), 200
