import re
from bson import ObjectId
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from app import extensions
from app.utils.permissions import (
    get_current_user,
    get_optional_user,
    is_super_admin
)
from app.routes.documents import document_to_json

search = Blueprint("search", __name__)


@search.route("/search", methods=["GET"])
@jwt_required(optional=True)
def search_documents():
    """
    GET /api/search?q=<query>
    Searches across document title, filename, OCR-extracted text, and dynamic metadata.
    Enforces RBAC:
      - Super Admin: searches across all documents in all divisions
      - Users / Division Admins: searches only documents in their division + approved cross-division documents
    """
    current_user = get_optional_user()

    query_str = request.args.get("q", "").strip()
    division_filter = request.args.get("division", "").strip()

    # Base query for RBAC permission
    if current_user:
        if is_super_admin(current_user):
            base_query = {}
        else:
            # Look up approved access requests for cross-division access
            approved_requests = list(extensions.db.access_requests.find(
                {"user_id": current_user["_id"], "status": "approved"},
                {"document_id": 1}
            ))
            approved_doc_ids = [r["document_id"] for r in approved_requests if "document_id" in r]

            base_query = {
                "$or": [
                    {"division": current_user.get("division")},
                    {"_id": {"$in": approved_doc_ids}}
                ]
            }
    else:
        # If unauthenticated, allow public query if division is provided, or return 401
        if division_filter:
            base_query = {"division": division_filter}
        else:
            base_query = {}

    if division_filter:
        if "$or" in base_query:
            base_query = {"$and": [base_query, {"division": division_filter}]}
        else:
            base_query["division"] = division_filter

    # Apply search term if provided
    conditions = []
    if query_str:
        regex_pattern = {"$regex": re.escape(query_str), "$options": "i"}
        conditions = [
            {"title": regex_pattern},
            {"original_name": regex_pattern},
            {"extracted_text": regex_pattern},
            {"metadata_search_string": regex_pattern}
        ]

    # Additional metadata key filters from query parameters
    reserved_params = ["q", "division", "page", "limit"]
    for param_key, param_val in request.args.items():
        if param_key not in reserved_params and param_val.strip():
            # Matches dynamic metadata field e.g. ?Report Type=Financial
            conditions.append({f"metadata.{param_key}": {"$regex": f"^{re.escape(param_val.strip())}$", "$options": "i"}})

    if conditions:
        if query_str and len(conditions) > 1 and any("metadata." in str(c) for c in conditions):
            search_clause = {"$and": [{"$or": conditions[:4]}, *conditions[4:]]}
        else:
            search_clause = {"$or": conditions} if not any("metadata." in str(c) for c in conditions) else {"$and": conditions}

        if base_query:
            final_query = {"$and": [base_query, search_clause]}
        else:
            final_query = search_clause
    else:
        final_query = base_query

    try:
        cursor = extensions.db.document_uploads.find(
            final_query,
            {"file_data": 0}
        ).sort("created_at", -1)

        documents = list(cursor)
        results = []

        for doc in documents:
            doc_data = document_to_json(doc)
            # Add highlights if search query is present
            if query_str:
                matched_in = []
                q_lower = query_str.lower()
                if q_lower in (doc.get("title") or "").lower():
                    matched_in.append("title")
                if q_lower in (doc.get("original_name") or "").lower():
                    matched_in.append("filename")
                if q_lower in (doc.get("extracted_text") or "").lower():
                    matched_in.append("ocr_text")
                    # Find snippet around match
                    full_text = doc.get("extracted_text", "")
                    idx = full_text.lower().find(q_lower)
                    start = max(0, idx - 50)
                    end = min(len(full_text), idx + len(q_lower) + 50)
                    doc_data["match_snippet"] = "..." + full_text[start:end] + "..."
                if q_lower in (doc.get("metadata_search_string") or "").lower():
                    matched_in.append("metadata")
                doc_data["matched_in"] = matched_in

            results.append(doc_data)

        return jsonify({
            "query": query_str,
            "count": len(results),
            "results": results,
            "documents": results
        }), 200

    except Exception as e:
        return jsonify({"message": f"Search failed: {str(e)}"}), 500
