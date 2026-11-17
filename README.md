# TRIAD AI - Intelligent Document Management System (DMS)

> A production-grade Document Management System featuring **Dynamic Custom Metadata**, **Role-Based Access Control (RBAC) with Division Isolation**, **Cross-Division Access Approvals**, **OCR Text Extraction**, and **Full-Text Multi-Field Search**.

---

## 🌟 Key Features & Core Requirements

1. **Dynamic Custom Metadata**:
   - Tag documents with extensible custom fields (e.g., `Report Type`, `Fiscal Year`, `Security Classification`, `Project Code`).
   - Admins can add, configure, and edit dynamic fields (Text, Number, Date, Dropdown options) at runtime without hardcoding.
2. **RBAC & Division Isolation**:
   - Strict division-level separation (`Finance`, `HR`, `Technical`, `Division A`, `Division B`).
   - Role hierarchy: `user`, `division_admin`, and `super_admin`.
   - By default, users can only upload, browse, preview, and download documents belonging to their own division.
3. **Cross-Division Access Workflow**:
   - Users who need access to another division's document can submit an access request (`POST /api/access/request`).
   - Only the admin of the document's owning division (or a super admin) can approve or reject the request.
   - Cross-division access requests cannot be approved by admins of unauthorized divisions.
   - Once approved, the requesting user receives immediate access to view, download, preview, and search the document.
4. **OCR & Text Extraction Engine**:
   - Extracts full textual content from uploaded PDF documents and images via `PyMuPDF` with `pytesseract` fallback for scanned pages.
   - Text is extracted automatically upon upload without breaking file storage.
   - OCR text is stored in MongoDB and indexed for instant searchability.
5. **Advanced Search Engine**:
   - `GET /api/search?q=<query>` searches across document titles, filenames, OCR-extracted contents, and dynamic metadata fields.
   - Filters by division and custom metadata (e.g., `?Report Type=Financial`).
   - Enforces RBAC permissions: users cannot discover or retrieve unauthorized documents.
6. **MongoDB GridFS Storage**:
   - File payloads are stored in MongoDB GridFS (`fs.files`, `fs.chunks`) for scalability and reliability.
7. **Complete Web UI (6 Required Views)**:
   - **Authentication**: Sign in / Sign up with division assignment.
   - **Document Hub / Dashboard**: Division & Report Type filters, upload button, document table.
   - **Document Details Page**: Dynamic metadata viewer, OCR text inspector, live preview, and download / request access buttons.
   - **Access Requests Inbox**: Incoming approvals (with One-Click Approve / Reject) and sent request tracking.
   - **Advanced Search Page**: Search across titles, metadata, and OCR text with match highlight badges.
   - **Admin / Settings Page**: Runtime dynamic metadata schema creator.

---

## 🏗️ Technology Stack

- **Backend**: Python 3.11+ / Flask, Flask-JWT-Extended, Flask-CORS, PyMongo, GridFS
- **OCR Engine**: PyMuPDF (`fitz`), Pillow, Pytesseract
- **Database**: MongoDB 7.0 (with GridFS and text indexing)
- **Frontend**: Responsive Single-Page Application (HTML5, Modern CSS, Vanilla JS, FontAwesome)
- **Containerization**: Docker & Docker Compose

---

## 🚀 Quick Start Guide

### Option 1: Run with Docker Compose (Recommended)

To launch the complete application and MongoDB in isolated containers:

```bash
docker compose up --build
```

The web application will be accessible at:
👉 **`http://localhost:5000`**

---

### Option 2: Run Locally (Windows / macOS / Linux)

#### 1. Prerequisites
- Python 3.10+
- MongoDB installed and running on port `27017`

#### 2. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

#### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Default configuration:
```env
MONGO_URI=mongodb://localhost:27017/
DATABASE_NAME=triad_dms
JWT_SECRET_KEY=triad_secret_development_key_2026
```

#### 4. (Optional) Initialize a Super Admin
```bash
python create_admin.py
```
Follow prompts to create a super admin account.

#### 5. Start the Server
```bash
python run.py
```
Visit **`http://localhost:5000`** in your browser to access the full frontend UI!

---

## 📡 REST API Reference

### 1. Authentication
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/register` | Register new user with division | No |
| `POST` | `/api/auth/login` | Login and receive JWT access token | No |

#### Register Payload:
```json
{
  "name": "Alex Smith",
  "email": "alex@triad.com",
  "division": "Finance",
  "password": "Password123!"
}
```

#### Login Response:
```json
{
  "token": "eyJhbGciOi...",
  "user": {
    "id": "6afc36803dcfbcc505e6bb62",
    "name": "Alex Smith",
    "email": "alex@triad.com",
    "division": "Finance",
    "role": "division_admin"
  }
}
```

---

### 2. Documents & Storage
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/documents/upload` | Multipart upload (file + metadata JSON), stores in GridFS and runs OCR | Optional / JWT |
| `GET` | `/api/documents` | List division documents + approved cross-division docs (supports `?Report Type=Financial`) | JWT |
| `GET` | `/api/documents/<id>` | Retrieve document metadata (enforces RBAC) | JWT |
| `GET` | `/api/documents/<id>/download` | Download file payload from GridFS | JWT |
| `GET` | `/api/documents/<id>/preview` | Stream file for inline browser preview | JWT |
| `GET` | `/api/documents/<id>/ocr` | Get OCR-extracted text content | JWT |

---

### 3. Cross-Division Access Requests
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/access/request` | Submit request (`{"document_id": "<id>"}`) | JWT |
| `POST` | `/api/access/approve` | Approve request (`{"request_id": "<id>"}`) | Owning Division Admin / Super Admin |
| `POST` | `/api/access/reject` | Reject request (`{"request_id": "<id>"}`) | Owning Division Admin / Super Admin |
| `GET` | `/api/access/requests` | List requests (scoped by user role) | JWT |

---

### 4. Advanced Search Engine
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/search?q=<query>` | Search across title, metadata, and OCR-extracted text | Optional / JWT |

Supports query parameters:
- `q`: Search keyword or phrase
- `division`: Filter by division
- Dynamic metadata keys: e.g. `?Report Type=Financial`

---

### 5. Dynamic Custom Metadata
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/metadata/active` | Get active fields for upload forms | JWT |
| `GET` | `/api/metadata` | List all metadata fields | Admin |
| `POST` | `/api/metadata` | Create a new custom metadata field | Admin |
| `DELETE` | `/api/metadata/<id>` | Deactivate a metadata field | Admin |

---

## 🧪 Automated Testing & Validation

The project includes the official evaluation test script along with comprehensive unit and integration test suites:

### 1. Run the Official Evaluation Suite
```bash
cd tests
python test_official_eval.py
```
Outputs `test_report.txt` verifying core requirements.

### 2. Run All Test Suites
```bash
# Regression suite for Modules 1–6 (29 tests)
python tests/test_existing_modules.py

# Access Request & Security Suite for Module 7 (30 tests)
python tests/test_module7_access.py

# OCR & Advanced Search Suite for Modules 8 & 9 (16 tests)
python tests/test_modules8_9.py
```
**Total: 75+ automated tests passing with 0 failures.**

---

## 📁 Project Architecture

```
triad-ai-dms/
├── backend/
│   ├── app/
│   │   ├── routes/
│   │   │   ├── auth.py             # User Authentication (Register/Login)
│   │   │   ├── users.py            # User & Division Management
│   │   │   ├── documents.py        # GridFS Storage, Upload & Preview
│   │   │   ├── metadata.py         # Dynamic Metadata Management
│   │   │   ├── access.py           # Cross-Division Approvals Workflow
│   │   │   └── search.py           # Full-Text & OCR Search Engine
│   │   ├── services/
│   │   │   └── ocr_service.py      # PyMuPDF & Tesseract Text Extraction
│   │   ├── utils/
│   │   │   └── permissions.py      # RBAC, Division Guards & Token Helpers
│   │   ├── extensions.py           # MongoDB, GridFS, JWT Initialization
│   │   └── __init__.py             # Flask Application Factory
│   ├── config.py                   # Configuration Settings
│   ├── create_admin.py             # CLI Admin Setup Utility
│   ├── requirements.txt            # Python Dependencies
│   └── run.py                      # Flask App Server & Static SPA Hosting
├── frontend/
│   ├── css/
│   │   └── style.css               # Modern Responsive Stylesheet
│   ├── js/
│   │   └── app.js                  # Frontend Controller & REST API Integration
│   └── index.html                  # Single-Page Application (6 Views)
├── tests/
│   ├── test_official_eval.py       # Starter evaluation test script
│   ├── test_existing_modules.py    # Modules 1–6 test suite
│   ├── test_module7_access.py      # Module 7 access workflow suite
│   └── test_modules8_9.py          # Modules 8 & 9 OCR & search suite
├── Dockerfile                      # Production Docker container
├── docker-compose.yml              # Multi-container orchestration (App + Mongo)
├── .env.example                    # Environment configuration template
├── .gitignore                      # Git exclusion rules
└── README.md                       # Documentation & Project Guide
```

---

## ⚖️ License
Developed for the TRIAD AI Full Stack Developer Internship Assignment.
