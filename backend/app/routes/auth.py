
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from datetime import timedelta
from app import extensions

auth = Blueprint("auth", __name__)


@auth.route("/register", methods=["POST"])
def register():

    data = request.get_json(silent=True) or {}

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    division = data.get("division", "").strip()

    if not all([name, email, password, division]):
        return jsonify({
            "message": "All fields are required"
        }), 400

    if len(password) < 8:
        return jsonify({
            "message": "Password must contain at least 8 characters"
        }), 400

    db = extensions.db

    if db is None:
        return jsonify({"message": "Database not initialized"}), 500

    if db.users.find_one({"email": email}):
        return jsonify({
            "message": "Email already registered"
        }), 409

    user = {
        "name": name,
        "email": email,
        "password": generate_password_hash(password),
        "division": division,
        "role": "user",
        "is_active": True
    }

    result = db.users.insert_one(user)

    return jsonify({
        "message": "Registration successful",
        "user_id": str(result.inserted_id)
    }), 201


@auth.route("/login", methods=["POST"])
def login():

    data = request.get_json(silent=True) or {}

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({
            "message": "Email and password required"
        }), 400

    db = extensions.db

    if db is None:
        return jsonify({"message": "Database not initialized"}), 500

    user = db.users.find_one({"email": email})

    if not user or not check_password_hash(
        user["password"], password
    ):
        return jsonify({
            "message": "Invalid email or password"
        }), 401

    if not user.get("is_active", True):
        return jsonify({
            "message": "Account is inactive"
        }), 403

    token = create_access_token(
        identity=str(user["_id"]),
        expires_delta=timedelta(hours=1)
    )

    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": {
            "id": str(user["_id"]),
            "name": user["name"],
            "email": user["email"],
            "division": user["division"],
            "role": user["role"]
        }
    }), 200
