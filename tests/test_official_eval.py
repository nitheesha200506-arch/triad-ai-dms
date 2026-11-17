import requests
import os
import json
import time

BASE_URL = "http://localhost:5000/api"
REPORT_FILE = "test_report.txt"

results = {"total": 0, "passed": 0, "failed": 0, "errors": []}

def log_result(test_name, success, error_msg=""):
    results["total"] += 1
    if success:
        results["passed"] += 1
    else:
        results["failed"] += 1
        results["errors"].append(f"[{test_name}] FAILED: {error_msg}")

def test_document_upload():
    url = f"{BASE_URL}/documents/upload"
    
    # Generate a simple 1KB dummy PDF for the test if it doesn't exist
    if not os.path.exists("test_sample.pdf"):
        with open("test_sample.pdf", "wb") as f:
            f.write(b"%PDF-1.4\n%" + b"A" * 1024 + b"\n%%EOF")

    try:
        with open("test_sample.pdf", "rb") as f:
            files = {"file": ("test_sample.pdf", f, "application/pdf")}
            # Simulating dynamic metadata extraction
            data = {"metadata": json.dumps({"Division": "Division A", "Report Type": "Financial"})}
            
            response = requests.post(url, files=files, data=data)
            
            if response.status_code in [200, 201]:
                log_result("POST /api/documents/upload", True)
                return response.json().get("document_id") or response.json().get("id")
            else:
                log_result("POST /api/documents/upload", False, f"Expected 200/201, got {response.status_code}. Response: {response.text}")
    except requests.exceptions.ConnectionError:
        log_result("POST /api/documents/upload", False, "Connection Refused. Is the Flask server running on port 5000?")
    except Exception as e:
        log_result("POST /api/documents/upload", False, str(e))
    return None

def test_authentication():
    unique_id = int(time.time())
    email = f"eval_user_{unique_id}@triad.com"
    password = "TestPassword123!"

    # 1. Register
    try:
        reg_res = requests.post(f"{BASE_URL}/auth/register", json={
            "name": "Eval User",
            "email": email,
            "password": password,
            "division": "Division A"
        })
        if reg_res.status_code in [200, 201]:
            log_result("POST /api/auth/register", True)
        else:
            log_result("POST /api/auth/register", False, f"Status: {reg_res.status_code}, Body: {reg_res.text}")
    except Exception as e:
        log_result("POST /api/auth/register", False, str(e))

    # 2. Login
    try:
        login_res = requests.post(f"{BASE_URL}/auth/login", json={
            "email": email,
            "password": password
        })
        if login_res.status_code == 200 and "token" in login_res.json():
            log_result("POST /api/auth/login", True)
            return login_res.json()["token"]
        else:
            log_result("POST /api/auth/login", False, f"Status: {login_res.status_code}")
    except Exception as e:
        log_result("POST /api/auth/login", False, str(e))
    return None

def test_rbac_isolation(token, doc_id):
    if not token or not doc_id:
        return

    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. List documents (Division A)
    try:
        list_res = requests.get(f"{BASE_URL}/documents", headers=headers)
        if list_res.status_code == 200:
            log_result("GET /api/documents (RBAC Scoped)", True)
        else:
            log_result("GET /api/documents (RBAC Scoped)", False, f"Status: {list_res.status_code}")
    except Exception as e:
        log_result("GET /api/documents (RBAC Scoped)", False, str(e))

    # 2. Download document
    try:
        dl_res = requests.get(f"{BASE_URL}/documents/{doc_id}/download", headers=headers)
        if dl_res.status_code == 200:
            log_result(f"GET /api/documents/{doc_id}/download", True)
        else:
            log_result(f"GET /api/documents/{doc_id}/download", False, f"Status: {dl_res.status_code}")
    except Exception as e:
        log_result(f"GET /api/documents/{doc_id}/download", False, str(e))

def test_search():
    try:
        search_res = requests.get(f"{BASE_URL}/search?q=Financial")
        if search_res.status_code == 200 and "results" in search_res.json():
            log_result("GET /api/search?q=Financial", True)
        else:
            log_result("GET /api/search?q=Financial", False, f"Status: {search_res.status_code}")
    except Exception as e:
        log_result("GET /api/search?q=Financial", False, str(e))

def generate_report():
    with open(REPORT_FILE, "w") as f:
        f.write("=== BACKEND API TEST REPORT ===\n")
        f.write(f"Total Endpoints Tested: {results['total']}\n")
        f.write(f"Passed: {results['passed']}\n")
        f.write(f"Failed: {results['failed']}\n\n")
        
        if results["failed"] > 0:
            f.write("=== FAILURE DETAILS ===\n")
            for error in results["errors"]:
                f.write(f"{error}\n")

if __name__ == "__main__":
    print(f"Running automated API tests against {BASE_URL}...")
    
    # Run tests
    doc_id = test_document_upload()
    token = test_authentication()
    test_rbac_isolation(token, doc_id)
    test_search()
    
    # Output report
    generate_report()
    print(f"Testing complete. Summary written to {REPORT_FILE}.")
