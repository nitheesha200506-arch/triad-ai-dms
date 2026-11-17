from datetime import datetime, timezone
from bson import ObjectId
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from pymongo.errors import PyMongoError

from app import extensions
from app.utils.permissions import (
    get_current_user,
    is_super_admin,
    is_division_admin,
    belongs_to_division,
    has_approved_cross_division_access
)

access = Blueprint("access", __name__)


def serialize_access_request(req, doc=None, user=None, decider=None):
    """Formats an access request document for API output."""
    data = {
        "id": str(req["_id"]),
        "document_id": str(req.get("document_id")),
        "user_id": str(req.get("user_id")),
        "document_division": req.get("document_division"),
        "requester_division": req.get("requester_division"),
        "status": req.get("status", "pending"),
        "created_at": req.get("created_at").isoformat() if req.get("created_at") else None,
        "decided_at": req.get("decided_at").isoformat() if req.get("decided_at") else None,
        "decided_by": str(req.get("decided_by")) if req.get("decided_by") else None
    }

    # Enrich with document and user information if available
    if doc:
        data["document_title"] = doc.get("title")
        data["document_filename"] = doc.get("original_name")
    if user:
        data["requester_name"] = user.get("name")
        data["requester_email"] = user.get("email")
    if decider:
        data["decided_by_name"] = decider.get("name")
        data["decided_by_email"] = decider.get("email")

    return data


@access.route("/request", methods=["POST"])
@jwt_required()
def request_access():
    """
    POST /api/access/request
    Submit a cross-division access request for a document.
    """
    current_user = get_current_user()
    if not current_user:
        return jsonify({"message": "User not found or inactive"}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"message": "Request body must be a JSON object"}), 400

    doc_id_str = data.get("doc_id") or data.get("document_id")
    if not doc_id_str or not ObjectId.is_valid(doc_id_str):
        return jsonify({"message": "Valid document_id or doc_id is required"}), 400

    doc_id = ObjectId(doc_id_str)
    document = extensions.db.document_uploads.find_one({"_id": doc_id})
    if not document:
        return jsonify({"message": "Document not found"}), 404

    doc_division = document.get("division")
    user_division = current_user.get("division")

    # Super admin already has access to everything
    if is_super_admin(current_user):
        return jsonify({"message": "Super administrators already have access to all documents"}), 400

    # User already belongs to document's division
    if belongs_to_division(current_user, doc_division):
        return jsonify({"message": "You already have access to documents in your own division"}), 400

    # Check if already approved
    if has_approved_cross_division_access(current_user, document):
        return jsonify({"message": "You already have approved access to this document"}), 409

    # Check if already has a pending request
    existing_pending = extensions.db.access_requests.find_one({
        "document_id": doc_id,
        "user_id": current_user["_id"],
        "status": "pending"
    })
    if existing_pending:
        return jsonify({"message": "An access request for this document is already pending"}), 409

    access_request = {
        "document_id": doc_id,
        "user_id": current_user["_id"],
        "document_division": doc_division,
        "requester_division": user_division,
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
        "decided_at": None,
        "decided_by": None
    }

    try:
        result = extensions.db.access_requests.insert_one(access_request)
        access_request["_id"] = result.inserted_id

        return jsonify({
            "message": "Access request submitted successfully",
            "request": serialize_access_request(access_request, doc=document, user=current_user)
        }), 201

    except PyMongoError:
        return jsonify({"message": "Database error while creating access request"}), 500


@access.route("/approve", methods=["POST"])
@jwt_required()
def approve_access():
    """
    POST /api/access/approve
    Approve a pending cross-division access request.
    Only the document's owning division admin or a super admin can approve.
    """
    current_user = get_current_user()
    if not current_user:
        return jsonify({"message": "User not found or inactive"}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"message": "Request body must be a JSON object"}), 400

    req_id_str = data.get("request_id")
    if not req_id_str or not ObjectId.is_valid(req_id_str):
        return jsonify({"message": "Valid request_id is required"}), 400

    req_id = ObjectId(req_id_str)
    access_req = extensions.db.access_requests.find_one({"_id": req_id})
    if not access_req:
        return jsonify({"message": "Access request not found"}), 404

    if access_req.get("status") != "pending":
        return jsonify({"message": f"Access request is already {access_req.get('status')}"}), 400

    # Authorization check:
    # Must be super_admin OR division_admin of the DOCUMENT'S division
    is_owning_division_admin = (
        is_division_admin(current_user)
        and belongs_to_division(current_user, access_req.get("document_division"))
    )

    if not (is_super_admin(current_user) or is_owning_division_admin):
        return jsonify({
            "message": "Permission denied. Only an administrator of the owning division or a super admin can approve this request"
        }), 403

    # Users must not approve their own requests
    if str(access_req.get("user_id")) == str(current_user["_id"]):
        return jsonify({"message": "You cannot approve your own access request"}), 403

    decided_at = datetime.now(timezone.utc)
    try:
        extensions.db.access_requests.update_one(
            {"_id": req_id},
            {
                "$set": {
                    "status": "approved",
                    "decided_at": decided_at,
                    "decided_by": current_user["_id"]
                }
            }
        )

        updated_req = extensions.db.access_requests.find_one({"_id": req_id})
        doc = extensions.db.document_uploads.find_one({"_id": updated_req.get("document_id")})
        requester = extensions.db.users.find_one({"_id": updated_req.get("user_id")})

        return jsonify({
            "message": "Access request approved successfully",
            "request": serialize_access_request(updated_req, doc=doc, user=requester, decider=current_user)
        }), 200

    except PyMongoError:
        return jsonify({"message": "Database error while approving access request"}), 500


@access.route("/reject", methods=["POST"])
@jwt_required()
def reject_access():
    """
    POST /api/access/reject
    Reject a pending cross-division access request.
    Only the document's owning division admin or a super admin can reject.
    """
    current_user = get_current_user()
    if not current_user:
        return jsonify({"message": "User not found or inactive"}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"message": "Request body must be a JSON object"}), 400

    req_id_str = data.get("request_id")
    if not req_id_str or not ObjectId.is_valid(req_id_str):
        return jsonify({"message": "Valid request_id is required"}), 400

    req_id = ObjectId(req_id_str)
    access_req = extensions.db.access_requests.find_one({"_id": req_id})
    if not access_req:
        return jsonify({"message": "Access request not found"}), 404

    if access_req.get("status") != "pending":
        return jsonify({"message": f"Access request is already {access_req.get('status')}"}), 400

    # Authorization check:
    is_owning_division_admin = (
        is_division_admin(current_user)
        and belongs_to_division(current_user, access_req.get("document_division"))
    )

    if not (is_super_admin(current_user) or is_owning_division_admin):
        return jsonify({
            "message": "Permission denied. Only an administrator of the owning division or a super admin can reject this request"
        }), 403

    # Users must not reject their own requests (should cancel if cancelled endpoint added)
    if str(access_req.get("user_id")) == str(current_user["_id"]):
        return jsonify({"message": "You cannot reject your own access request"}), 403

    decided_at = datetime.now(timezone.utc)
    try:
        extensions.db.access_requests.update_one(
            {"_id": req_id},
            {
                "$set": {
                    "status": "rejected",
                    "decided_at": decided_at,
                    "decided_by": current_user["_id"]
                }
            }
        )

        updated_req = extensions.db.access_requests.find_one({"_id": req_id})
        doc = extensions.db.document_uploads.find_one({"_id": updated_req.get("document_id")})
        requester = extensions.db.users.find_one({"_id": updated_req.get("user_id")})

        return jsonify({
            "message": "Access request rejected successfully",
            "request": serialize_access_request(updated_req, doc=doc, user=requester, decider=current_user)
        }), 200

    except PyMongoError:
        return jsonify({"message": "Database error while rejecting access request"}), 500


@access.route("/requests", methods=["GET"])
@jwt_required()
def get_access_requests():
    """
    GET /api/access/requests
    List access requests with role-based scoping:
      - Super Admin: sees all requests
      - Division Admin: sees requests for their division's documents AND requests by their division's users
      - Regular User: sees only requests they submitted
    Optional query parameter: status (pending, approved, rejected)
    """
    current_user = get_current_user()
    if not current_user:
        return jsonify({"message": "User not found or inactive"}), 401

    status_filter = request.args.get("status")

    query = {}
    if status_filter in ["pending", "approved", "rejected"]:
        query["status"] = status_filter

    if is_super_admin(current_user):
        pass  # Super admin sees all matching query
    elif is_division_admin(current_user):
        user_div = current_user.get("division")
        division_filter = {
            "$or": [
                {"document_division": user_div},
                {"requester_division": user_div}
            ]
        }
        if query:
            query = {"$and": [query, division_filter]}
        else:
            query = division_filter
    else:
        # Regular user only sees their own requests
        query["user_id"] = current_user["_id"]

    try:
        cursor = extensions.db.access_requests.find(query).sort("created_at", -1)
        raw_requests = list(cursor)

        # Batch lookup documents and users for efficiency
        doc_ids = [r["document_id"] for r in raw_requests if r.get("document_id")]
        user_ids = [r["user_id"] for r in raw_requests if r.get("user_id")]
        decider_ids = [r["decided_by"] for r in raw_requests if r.get("decided_by")]

        docs_map = {
            d["_id"]: d
            for d in extensions.db.document_uploads.find(
                {"_id": {"$in": doc_ids}},
                {"title": 1, "original_name": 1, "division": 1}
            )
        }
        users_map = {
            u["_id"]: u
            for u in extensions.db.users.find(
                {"_id": {"$in": list(set(user_ids + decider_ids))}},
                {"name": 1, "email": 1, "division": 1}
            )
        }

        serialized = [
            serialize_access_request(
                r,
                doc=docs_map.get(r.get("document_id")),
                user=users_map.get(r.get("user_id")),
                decider=users_map.get(r.get("decided_by"))
            )
            for r in raw_requests
        ]

        return jsonify({
            "count": len(serialized),
            "requests": serialized
        }), 200

    except PyMongoError:
        return jsonify({"message": "Database error while fetching access requests"}), 500
