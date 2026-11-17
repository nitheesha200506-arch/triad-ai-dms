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

def run_tests():
    print("=" * 60)
    print("RUNNING COMPREHENSIVE VERIFICATION FOR MODULES 1 - 6")
    print("=" * 60)

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

    # Ensure DB is connected
    with app.app_context():
        db = extensions.db
        assert_test("Database connection ping", db is not None)

        # ----------------------------------------------------
        # MODULE 1: AUTHENTICATION TESTS
        # ----------------------------------------------------
        print("\n--- Testing Module 1: Authentication ---")
        test_email = f"test_verify_{int(datetime.now().timestamp())}@triad.com"
        test_password = "SecurePassword123!"

        # 1.1 Register
        reg_res = client.post("/api/auth/register", json={
            "name": "Verification User",
            "email": test_email,
            "password": test_password,
            "division": "HR"
        })
        assert_test("Register new user (201)", reg_res.status_code == 201, reg_res.get_data(as_text=True))
        reg_data = reg_res.get_json() or {}
        new_user_id = reg_data.get("user_id")

        # 1.2 Duplicate register
        dup_res = client.post("/api/auth/register", json={
            "name": "Verification User Duplicate",
            "email": test_email,
            "password": test_password,
            "division": "HR"
        })
        assert_test("Duplicate email registration returns 409", dup_res.status_code == 409)

        # 1.3 Short password
        short_res = client.post("/api/auth/register", json={
            "name": "Short Pwd",
            "email": f"short_{int(datetime.now().timestamp())}@triad.com",
            "password": "123",
            "division": "HR"
        })
        assert_test("Password < 8 chars returns 400", short_res.status_code == 400)

        # 1.4 Login with valid credentials
        login_res = client.post("/api/auth/login", json={
            "email": test_email,
            "password": test_password
        })
        assert_test("Login with valid credentials (200)", login_res.status_code == 200)
        login_data = login_res.get_json() or {}
        user_token = login_data.get("token")
        assert_test("Token generated on login", bool(user_token))

        # 1.5 Login with invalid password
        bad_login = client.post("/api/auth/login", json={
            "email": test_email,
            "password": "WrongPassword!"
        })
        assert_test("Login with incorrect password returns 401", bad_login.status_code == 401)

        # Generate tokens for existing test roles in database
        super_admin = db.users.find_one({"role": "super_admin", "is_active": True})
        finance_admin = db.users.find_one({"role": "division_admin", "division": "Finance", "is_active": True})
        hr_user = db.users.find_one({"_id": ObjectId(new_user_id)})

        super_token = create_access_token(identity=str(super_admin["_id"])) if super_admin else None
        finance_admin_token = create_access_token(identity=str(finance_admin["_id"])) if finance_admin else None

        auth_headers_user = {"Authorization": f"Bearer {user_token}"}
        auth_headers_super = {"Authorization": f"Bearer {super_token}"}
        auth_headers_finance = {"Authorization": f"Bearer {finance_admin_token}"}

        # ----------------------------------------------------
        # MODULE 2 & 3: USERS & DIVISIONS
        # ----------------------------------------------------
        print("\n--- Testing Modules 2 & 3: Users & Divisions ---")

        # 2.1 Get divisions
        div_res = client.get("/api/divisions", headers=auth_headers_user)
        assert_test("GET /api/divisions returns 200", div_res.status_code == 200)
        divisions = [d["name"] for d in div_res.get_json().get("divisions", [])]
        assert_test("Divisions contain Finance, HR, Technical", 
                    all(x in divisions for x in ["Finance", "HR", "Technical"]))

        # 2.2 Role-based user listing
        unauth_users = client.get("/api/users")
        assert_test("GET /api/users without token returns 401", unauth_users.status_code == 401)

        user_users = client.get("/api/users", headers=auth_headers_user)
        assert_test("GET /api/users as regular user returns 403", user_users.status_code == 403)

        fin_users = client.get("/api/users", headers=auth_headers_finance)
        assert_test("GET /api/users as division admin returns 200", fin_users.status_code == 200)
        fin_list = fin_users.get_json().get("users", [])
        assert_test("Division admin only sees their own division", 
                    all(u["division"] == "Finance" for u in fin_list))

        super_users = client.get("/api/users", headers=auth_headers_super)
        assert_test("GET /api/users as super admin returns 200 and all users", 
                    super_users.status_code == 200 and len(super_users.get_json().get("users", [])) >= 3)

        # 2.3 User update
        update_res = client.put(f"/api/users/{new_user_id}", headers=auth_headers_super, json={
            "name": "Verification User Updated"
        })
        assert_test("Super admin can update user name (200)", update_res.status_code == 200)

        # ----------------------------------------------------
        # MODULE 4 & 5: DOCUMENTS UPLOAD, RETRIEVAL, PREVIEW, DOWNLOAD
        # ----------------------------------------------------
        print("\n--- Testing Modules 4 & 5: Documents ---")

        # Valid PDF header: %PDF-1.4 ...
        fake_pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        
        # 4.1 Upload valid PDF as Finance admin
        upload_res = client.post("/api/documents/upload", headers=auth_headers_finance, data={
            "file": (io.BytesIO(fake_pdf_content), "test_doc.pdf"),
            "title": "Finance Test PDF",
            "metadata": json.dumps({"category": "audit", "year": 2026})
        }, content_type="multipart/form-data")
        assert_test("Upload document with valid PDF signature (201)", upload_res.status_code == 201)
        upload_data = upload_res.get_json() or {}
        doc_id = upload_data.get("document_id")

        # 4.2 Upload invalid file type
        bad_upload = client.post("/api/documents/upload", headers=auth_headers_finance, data={
            "file": (io.BytesIO(b"malicious script"), "test.exe"),
            "title": "Bad File"
        }, content_type="multipart/form-data")
        assert_test("Upload invalid file type returns 400", bad_upload.status_code == 400)

        # 4.3 Upload PDF with spoofed extension but invalid header
        spoofed = client.post("/api/documents/upload", headers=auth_headers_finance, data={
            "file": (io.BytesIO(b"NOT A REAL PDF HEADER"), "fake.pdf"),
            "title": "Fake PDF"
        }, content_type="multipart/form-data")
        assert_test("Upload spoofed PDF signature returns 400", spoofed.status_code == 400)

        # 5.1 Same division document retrieval
        same_div_res = client.get(f"/api/documents/{doc_id}", headers=auth_headers_finance)
        assert_test("Finance admin can access Finance document (200)", same_div_res.status_code == 200)

        # 5.2 Super admin document retrieval
        super_doc_res = client.get(f"/api/documents/{doc_id}", headers=auth_headers_super)
        assert_test("Super admin can access any document (200)", super_doc_res.status_code == 200)

        # 5.3 Cross division document retrieval without approved access (HR user attempting Finance doc)
        cross_div_res = client.get(f"/api/documents/{doc_id}", headers=auth_headers_user)
        assert_test("HR user denied access to Finance document without approval (403)", cross_div_res.status_code == 403)

        # 5.4 Document preview
        preview_res = client.get(f"/api/documents/{doc_id}/preview", headers=auth_headers_finance)
        assert_test("Preview returns 200 and application/pdf", 
                    preview_res.status_code == 200 and preview_res.mimetype == "application/pdf")
        assert_test("Preview has X-Content-Type-Options: nosniff header", 
                    preview_res.headers.get("X-Content-Type-Options") == "nosniff")

        # 5.5 Document download
        download_res = client.get(f"/api/documents/{doc_id}/download", headers=auth_headers_finance)
        assert_test("Download returns 200 and attachment", 
                    download_res.status_code == 200 and "attachment" in download_res.headers.get("Content-Disposition", ""))

        # ----------------------------------------------------
        # MODULE 6: DYNAMIC METADATA
        # ----------------------------------------------------
        print("\n--- Testing Module 6: Dynamic Metadata Fields ---")

        field_name = f"test_meta_{int(datetime.now().timestamp())}"

        # 6.1 Regular user cannot create metadata
        user_meta = client.post("/api/metadata", headers=auth_headers_user, json={
            "field_name": field_name,
            "field_type": "text"
        })
        assert_test("Regular user cannot create metadata field (403)", user_meta.status_code == 403)

        # 6.2 Admin creates metadata field
        create_meta = client.post("/api/metadata", headers=auth_headers_super, json={
            "field_name": field_name,
            "field_type": "dropdown",
            "options": ["Option A", "Option B"],
            "required": True
        })
        assert_test("Super admin can create dropdown metadata field (201)", create_meta.status_code == 201)
        meta_id = (create_meta.get_json() or {}).get("field", {}).get("id")

        # 6.3 Duplicate metadata field name returns 409
        dup_meta = client.post("/api/metadata", headers=auth_headers_super, json={
            "field_name": field_name.upper(),  # case-insensitive check
            "field_type": "text"
        })
        assert_test("Duplicate metadata field returns 409", dup_meta.status_code == 409)

        # 6.4 Get metadata list
        list_meta = client.get("/api/metadata", headers=auth_headers_super)
        assert_test("GET /api/metadata returns 200", list_meta.status_code == 200)

        # 6.5 Deactivate metadata field
        deact_meta = client.delete(f"/api/metadata/{meta_id}", headers=auth_headers_super)
        assert_test("DELETE /api/metadata/<id> deactivates field (200)", deact_meta.status_code == 200)

        # ----------------------------------------------------
        # CLEANUP TEST ARTIFACTS
        # ----------------------------------------------------
        print("\n--- Cleaning up temporary test records ---")
        if new_user_id:
            db.users.delete_one({"_id": ObjectId(new_user_id)})
        if doc_id:
            db.document_uploads.delete_one({"_id": ObjectId(doc_id)})
        if meta_id:
            db.metadata_fields.delete_one({"_id": ObjectId(meta_id)})
        print("  [INFO] Temporary test records cleaned up cleanly.")

    print("\n" + "=" * 60)
    print(f"VERIFICATION RESULTS: {passed} PASSED, {failed} FAILED")
    print("=" * 60)
    return failed == 0

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
