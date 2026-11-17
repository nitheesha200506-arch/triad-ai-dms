import os
import sys
import io
import json
from bson import ObjectId
from datetime import datetime, timezone

# Add backend directory to sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from run import app
from app import extensions
from flask_jwt_extended import create_access_token


def run_module7_tests():
    print("=" * 65)
    print("RUNNING COMPREHENSIVE VERIFICATION FOR MODULE 7 (ACCESS REQUESTS)")
    print("=" * 65)

    client = app.test_client()
    passed = 0
    failed = 0

    def assert_test(name, condition, details=""):
        nonlocal passed, failed
        if condition:
            print(f"  [PASS] {name}")
            passed += 1
        else:
            print(f"  [FAIL] {name} - {details}")
            failed += 1

    with app.app_context():
        db = extensions.db

        # Find or create test users
        super_admin = db.users.find_one({"role": "super_admin", "is_active": True})
        finance_admin = db.users.find_one({"role": "division_admin", "division": "Finance", "is_active": True})

        # Ensure we have an HR user and an HR admin
        hr_user = db.users.find_one({"role": "user", "division": "HR", "is_active": True})
        if not hr_user:
            hr_user_id = db.users.insert_one({
                "name": "HR Test User",
                "email": f"hr_user_{int(datetime.now().timestamp())}@triad.com",
                "password": "hashed_pw",
                "division": "HR",
                "role": "user",
                "is_active": True
            }).inserted_id
            hr_user = db.users.find_one({"_id": hr_user_id})

        hr_admin = db.users.find_one({"role": "division_admin", "division": "HR", "is_active": True})
        created_hr_admin = False
        if not hr_admin:
            hr_admin_id = db.users.insert_one({
                "name": "HR Test Admin",
                "email": f"hr_admin_{int(datetime.now().timestamp())}@triad.com",
                "password": "hashed_pw",
                "division": "HR",
                "role": "division_admin",
                "is_active": True
            }).inserted_id
            hr_admin = db.users.find_one({"_id": hr_admin_id})
            created_hr_admin = True

        super_token = create_access_token(identity=str(super_admin["_id"]))
        fin_admin_token = create_access_token(identity=str(finance_admin["_id"]))
        hr_user_token = create_access_token(identity=str(hr_user["_id"]))
        hr_admin_token = create_access_token(identity=str(hr_admin["_id"]))

        headers_super = {"Authorization": f"Bearer {super_token}"}
        headers_fin_admin = {"Authorization": f"Bearer {fin_admin_token}"}
        headers_hr_user = {"Authorization": f"Bearer {hr_user_token}"}
        headers_hr_admin = {"Authorization": f"Bearer {hr_admin_token}"}

        # Create a Finance Document
        fake_pdf = b"%PDF-1.4\nFinance Q4 Audit Data\n%%EOF"
        upload_res = client.post("/api/documents/upload", headers=headers_fin_admin, data={
            "file": (io.BytesIO(fake_pdf), "finance_q4.pdf"),
            "title": "Finance Q4 Report",
            "metadata": json.dumps({"year": 2026, "department": "Finance"})
        }, content_type="multipart/form-data")
        assert_test("Finance Admin creates Finance Document (201)", upload_res.status_code == 201)
        doc_id = upload_res.get_json().get("document_id")

        # Create a second Finance Document for rejection test
        upload_res2 = client.post("/api/documents/upload", headers=headers_fin_admin, data={
            "file": (io.BytesIO(fake_pdf), "finance_rejected.pdf"),
            "title": "Finance Sensitive Report",
            "metadata": json.dumps({"year": 2026})
        }, content_type="multipart/form-data")
        doc_id_rejected = upload_res2.get_json().get("document_id")

        # -----------------------------------------------------------------
        # TEST 1: Request Access (HR user -> Finance Document)
        # -----------------------------------------------------------------
        print("\n--- Test 1: Access Request Submission ---")
        req_res = client.post("/api/access/request", headers=headers_hr_user, json={
            "document_id": doc_id
        })
        assert_test("HR user submits access request (201)", req_res.status_code == 201)
        req_data = req_res.get_json().get("request", {})
        request_id = req_data.get("id")
        assert_test("Request status is 'pending'", req_data.get("status") == "pending")
        assert_test("Document division is 'Finance'", req_data.get("document_division") == "Finance")
        assert_test("Requester division is 'HR'", req_data.get("requester_division") == "HR")

        # -----------------------------------------------------------------
        # TEST 2: Duplicate Request Prevention
        # -----------------------------------------------------------------
        print("\n--- Test 2: Duplicate Request Prevention ---")
        dup_req = client.post("/api/access/request", headers=headers_hr_user, json={
            "document_id": doc_id
        })
        assert_test("Duplicate pending request returns 409", dup_req.status_code == 409)

        # -----------------------------------------------------------------
        # TEST 3: Own Division Request Prevention
        # -----------------------------------------------------------------
        print("\n--- Test 3: Own Division / Super Admin Guardrails ---")
        own_req = client.post("/api/access/request", headers=headers_fin_admin, json={
            "document_id": doc_id
        })
        assert_test("User cannot request access to own division document (400)", own_req.status_code == 400)

        super_req = client.post("/api/access/request", headers=headers_super, json={
            "document_id": doc_id
        })
        assert_test("Super admin cannot request access (already has access) (400)", super_req.status_code == 400)

        # -----------------------------------------------------------------
        # TEST 4: Document Access BLOCKED before Approval
        # -----------------------------------------------------------------
        print("\n--- Test 4: Document Access Denied While Pending ---")
        unapproved_get = client.get(f"/api/documents/{doc_id}", headers=headers_hr_user)
        assert_test("HR user cannot view document while request is pending (403)", unapproved_get.status_code == 403)

        unapproved_dl = client.get(f"/api/documents/{doc_id}/download", headers=headers_hr_user)
        assert_test("HR user cannot download document while request is pending (403)", unapproved_dl.status_code == 403)

        # -----------------------------------------------------------------
        # TEST 5: Security - HR Admin MUST NOT Approve Finance Request
        # -----------------------------------------------------------------
        print("\n--- Test 5: Strict Security Check - Cross-division Admin Approval ---")
        unauth_approve = client.post("/api/access/approve", headers=headers_hr_admin, json={
            "request_id": request_id
        })
        assert_test("HR admin CANNOT approve Finance request (403)", unauth_approve.status_code == 403)

        # -----------------------------------------------------------------
        # TEST 6: Finance Admin Approves the Request
        # -----------------------------------------------------------------
        print("\n--- Test 6: Authorized Approval ---")
        auth_approve = client.post("/api/access/approve", headers=headers_fin_admin, json={
            "request_id": request_id
        })
        assert_test("Finance admin approves request successfully (200)", auth_approve.status_code == 200)
        approved_data = auth_approve.get_json().get("request", {})
        assert_test("Status changed to 'approved'", approved_data.get("status") == "approved")
        assert_test("Decided by set to Finance admin", approved_data.get("decided_by") == str(finance_admin["_id"]))

        # -----------------------------------------------------------------
        # TEST 7: Document Access GRANTED after Approval
        # -----------------------------------------------------------------
        print("\n--- Test 7: Document Access Verified After Approval ---")
        approved_get = client.get(f"/api/documents/{doc_id}", headers=headers_hr_user)
        assert_test("HR user can now view document metadata (200)", approved_get.status_code == 200)

        approved_dl = client.get(f"/api/documents/{doc_id}/download", headers=headers_hr_user)
        assert_test("HR user can now download document (200)", approved_dl.status_code == 200)

        approved_prev = client.get(f"/api/documents/{doc_id}/preview", headers=headers_hr_user)
        assert_test("HR user can now preview document (200)", approved_prev.status_code == 200)

        user_doc_list = client.get("/api/documents", headers=headers_hr_user)
        listed_doc_ids = [d["id"] for d in user_doc_list.get_json().get("documents", [])]
        assert_test("Approved document appears in user's /api/documents list", doc_id in listed_doc_ids)

        # -----------------------------------------------------------------
        # TEST 8: Cannot re-approve already decided request
        # -----------------------------------------------------------------
        print("\n--- Test 8: Re-decision Prevention ---")
        reapprove = client.post("/api/access/approve", headers=headers_fin_admin, json={
            "request_id": request_id
        })
        assert_test("Cannot approve already approved request (400)", reapprove.status_code == 400)

        # -----------------------------------------------------------------
        # TEST 9: Rejection Workflow
        # -----------------------------------------------------------------
        print("\n--- Test 9: Rejection Workflow ---")
        req_res2 = client.post("/api/access/request", headers=headers_hr_user, json={
            "document_id": doc_id_rejected
        })
        assert_test("HR user requests second document (201)", req_res2.status_code == 201)
        request_id_2 = req_res2.get_json().get("request", {}).get("id")

        # HR Admin cannot reject
        hr_reject = client.post("/api/access/reject", headers=headers_hr_admin, json={
            "request_id": request_id_2
        })
        assert_test("HR admin CANNOT reject Finance request (403)", hr_reject.status_code == 403)

        # Finance Admin rejects
        fin_reject = client.post("/api/access/reject", headers=headers_fin_admin, json={
            "request_id": request_id_2
        })
        assert_test("Finance admin rejects request (200)", fin_reject.status_code == 200)
        assert_test("Status changed to 'rejected'", fin_reject.get_json().get("request", {}).get("status") == "rejected")

        # HR user still denied access
        rejected_access = client.get(f"/api/documents/{doc_id_rejected}", headers=headers_hr_user)
        assert_test("HR user is denied access to rejected document (403)", rejected_access.status_code == 403)

        # -----------------------------------------------------------------
        # TEST 10: GET /api/access/requests (Role-Based Visibility)
        # -----------------------------------------------------------------
        print("\n--- Test 10: Access Requests Listing Scopes ---")
        
        # User sees only their requests
        user_reqs = client.get("/api/access/requests", headers=headers_hr_user)
        assert_test("User sees their own requests (200)", user_reqs.status_code == 200)
        user_list = user_reqs.get_json().get("requests", [])
        assert_test("All user requests belong to HR user", 
                    all(r["user_id"] == str(hr_user["_id"]) for r in user_list))

        # Finance admin sees incoming Finance requests
        fin_reqs = client.get("/api/access/requests", headers=headers_fin_admin)
        assert_test("Finance admin gets requests (200)", fin_reqs.status_code == 200)
        fin_list = fin_reqs.get_json().get("requests", [])
        assert_test("Finance admin sees requests involving Finance division", 
                    all(r["document_division"] == "Finance" or r["requester_division"] == "Finance" for r in fin_list))

        # Super admin sees all requests
        super_reqs = client.get("/api/access/requests", headers=headers_super)
        assert_test("Super admin sees all requests (200)", super_reqs.status_code == 200)

        # Filter by status
        pending_reqs = client.get("/api/access/requests?status=approved", headers=headers_super)
        assert_test("Filter by status=approved works", 
                    all(r["status"] == "approved" for r in pending_reqs.get_json().get("requests", [])))

        # -----------------------------------------------------------------
        # CLEANUP
        # -----------------------------------------------------------------
        print("\n--- Cleaning up temporary test artifacts ---")
        db.access_requests.delete_many({"document_id": {"$in": [ObjectId(doc_id), ObjectId(doc_id_rejected)]}})
        db.document_uploads.delete_many({"_id": {"$in": [ObjectId(doc_id), ObjectId(doc_id_rejected)]}})
        if created_hr_admin:
            db.users.delete_one({"_id": hr_admin["_id"]})
        print("  [INFO] Temporary records cleaned up successfully.")

    print("\n" + "=" * 65)
    print(f"MODULE 7 VERIFICATION RESULTS: {passed} PASSED, {failed} FAILED")
    print("=" * 65)
    return failed == 0


if __name__ == "__main__":
    success = run_module7_tests()
    sys.exit(0 if success else 1)
