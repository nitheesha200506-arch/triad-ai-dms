import os
import sys
import io
import json
from bson import ObjectId
from datetime import datetime

# Add backend directory to sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from run import app
from app import extensions
from flask_jwt_extended import create_access_token
import pymupdf


def create_test_pdf_with_text(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def run_modules8_9_tests():
    print("=" * 65)
    print("RUNNING COMPREHENSIVE VERIFICATION FOR MODULES 8 & 9 (OCR & SEARCH)")
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

        super_admin = db.users.find_one({"role": "super_admin", "is_active": True})
        finance_admin = db.users.find_one({"role": "division_admin", "division": "Finance", "is_active": True})
        hr_user = db.users.find_one({"role": "user", "division": "HR", "is_active": True})

        super_token = create_access_token(identity=str(super_admin["_id"]))
        fin_admin_token = create_access_token(identity=str(finance_admin["_id"]))
        hr_user_token = create_access_token(identity=str(hr_user["_id"]))

        headers_super = {"Authorization": f"Bearer {super_token}"}
        headers_fin = {"Authorization": f"Bearer {fin_admin_token}"}
        headers_hr = {"Authorization": f"Bearer {hr_user_token}"}

        # ----------------------------------------------------
        # MODULE 8: OCR & TEXT EXTRACTION TESTS
        # ----------------------------------------------------
        print("\n--- Testing Module 8: OCR Extraction ---")

        unique_keyword = f"ConfidentialAlpha_{int(datetime.now().timestamp())}"
        pdf_content = create_test_pdf_with_text(f"TRIAD AI Quarterly Earnings Analysis. Key Code: {unique_keyword}.")

        # 8.1 Upload PDF with text
        upload_res = client.post("/api/documents/upload", headers=headers_fin, data={
            "file": (io.BytesIO(pdf_content), "quarterly_earnings.pdf"),
            "title": "Quarterly Earnings Report",
            "metadata": json.dumps({"Report Type": "Financial", "Year": 2026, "Category": "Audit"})
        }, content_type="multipart/form-data")

        assert_test("Upload document with dynamic metadata (201)", upload_res.status_code == 201)
        upload_data = upload_res.get_json() or {}
        doc_id = upload_data.get("document_id")

        # 8.2 Verify OCR extracted text
        assert_test("OCR extracted text contains unique keyword", unique_keyword in upload_data.get("extracted_text", ""))

        # 8.3 Verify GridFS file was created
        doc_in_db = db.document_uploads.find_one({"_id": ObjectId(doc_id)})
        assert_test("GridFS file_id stored in document", bool(doc_in_db.get("gridfs_id")))
        if doc_in_db.get("gridfs_id"):
            grid_out = extensions.fs.get(ObjectId(doc_in_db["gridfs_id"]))
            assert_test("GridFS file payload matches uploaded bytes", grid_out.read() == pdf_content)

        # 8.4 Authenticated OCR Endpoint
        ocr_res = client.get(f"/api/documents/{doc_id}/ocr", headers=headers_fin)
        assert_test("Finance admin can get OCR text via /api/documents/<id>/ocr (200)", ocr_res.status_code == 200)
        assert_test("OCR endpoint returns extracted_text", unique_keyword in ocr_res.get_json().get("extracted_text", ""))

        # 8.5 OCR Access Control: HR user denied access to Finance OCR
        hr_ocr = client.get(f"/api/documents/{doc_id}/ocr", headers=headers_hr)
        assert_test("HR user denied access to Finance document OCR text (403)", hr_ocr.status_code == 403)

        # ----------------------------------------------------
        # MODULE 9: ADVANCED SEARCH TESTS
        # ----------------------------------------------------
        print("\n--- Testing Module 9: Search Engine & Filtering ---")

        # 9.1 Search by OCR extracted keyword (Finance Admin)
        search_ocr = client.get(f"/api/search?q={unique_keyword}", headers=headers_fin)
        assert_test("Search by OCR keyword returns 200", search_ocr.status_code == 200)
        results = search_ocr.get_json().get("results", [])
        assert_test("Search finds document by OCR text", any(d["id"] == doc_id for d in results))

        # 9.2 Search RBAC Isolation: HR user cannot find Finance document via search
        hr_search = client.get(f"/api/search?q={unique_keyword}", headers=headers_hr)
        assert_test("HR user search returns 200", hr_search.status_code == 200)
        hr_results = hr_search.get_json().get("results", [])
        assert_test("HR user cannot discover Finance document in search results", not any(d["id"] == doc_id for d in hr_results))

        # 9.3 Super admin can find document across all divisions
        super_search = client.get(f"/api/search?q={unique_keyword}", headers=headers_super)
        super_results = super_search.get_json().get("results", [])
        assert_test("Super admin finds document in search results", any(d["id"] == doc_id for d in super_results))

        # 9.4 Search by dynamic metadata (e.g. ?Report Type=Financial)
        meta_search = client.get("/api/search?Report Type=Financial", headers=headers_fin)
        assert_test("Search by dynamic metadata field returns 200", meta_search.status_code == 200)
        meta_results = meta_search.get_json().get("results", [])
        assert_test("Metadata search finds matching document", any(d["id"] == doc_id for d in meta_results))

        # 9.5 GET /api/documents with dynamic metadata filter (?Report Type=Financial)
        filter_docs = client.get("/api/documents?Report Type=Financial", headers=headers_fin)
        assert_test("GET /api/documents?Report Type=Financial returns 200", filter_docs.status_code == 200)
        filter_results = filter_docs.get_json().get("documents", [])
        assert_test("Filtered document list includes uploaded document", any(d["id"] == doc_id for d in filter_results))

        # ----------------------------------------------------
        # CLEANUP
        # ----------------------------------------------------
        print("\n--- Cleaning up temporary test records ---")
        if doc_in_db.get("gridfs_id"):
            try:
                extensions.fs.delete(ObjectId(doc_in_db["gridfs_id"]))
            except Exception:
                pass
        db.document_uploads.delete_one({"_id": ObjectId(doc_id)})
        print("  [INFO] Cleaned up temporary test documents.")

    print("\n" + "=" * 65)
    print(f"MODULES 8 & 9 VERIFICATION RESULTS: {passed} PASSED, {failed} FAILED")
    print("=" * 65)
    return failed == 0


if __name__ == "__main__":
    success = run_modules8_9_tests()
    sys.exit(0 if success else 1)
