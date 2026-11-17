/**
 * TRIAD AI DMS - Frontend Application Controller
 * Connects directly to Flask REST API
 */

const API_BASE = "/api";

let currentUser = null;
let authToken = localStorage.getItem("triad_token");
let activeMetadataFields = [];
let cachedDocuments = [];
let currentDocInModal = null;
let currentRequestTab = "incoming";

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

async function initApp() {
  await loadDivisionsDropdown();
  if (authToken) {
    const savedUser = localStorage.getItem("triad_user");
    if (savedUser) {
      try {
        currentUser = JSON.parse(savedUser);
        setupUserSession();
        return;
      } catch (e) {
        localStorage.removeItem("triad_user");
      }
    }
  }
  showAuthOverlay();
}

function showAuthOverlay() {
  document.getElementById("authOverlay").style.display = "flex";
  document.getElementById("appContainer").style.display = "none";
}

function hideAuthOverlay() {
  document.getElementById("authOverlay").style.display = "none";
  document.getElementById("appContainer").style.display = "flex";
}

function switchAuthTab(tab) {
  const tabs = document.querySelectorAll(".auth-tab");
  tabs.forEach(t => t.classList.remove("active"));
  
  if (tab === "login") {
    tabs[0].classList.add("active");
    document.getElementById("loginForm").style.display = "block";
    document.getElementById("registerForm").style.display = "none";
  } else {
    tabs[1].classList.add("active");
    document.getElementById("loginForm").style.display = "none";
    document.getElementById("registerForm").style.display = "block";
  }
}

async function loadDivisionsDropdown() {
  try {
    const res = await fetch(`${API_BASE}/divisions`, {
      headers: authToken ? { "Authorization": `Bearer ${authToken}` } : {}
    });
    if (res.ok) {
      const data = await res.json();
      const divisions = data.divisions || [];
      const regSelect = document.getElementById("regDivision");
      const filterSelect = document.getElementById("divisionFilter");
      const advFilterSelect = document.getElementById("advDivisionFilter");

      let html = '<option value="">Select Division...</option>';
      let filterHtml = '<option value="">All Divisions</option>';

      divisions.forEach(d => {
        html += `<option value="${d.name}">${d.name}</option>`;
        filterHtml += `<option value="${d.name}">${d.name}</option>`;
      });

      if (regSelect) regSelect.innerHTML = html;
      if (filterSelect) filterSelect.innerHTML = filterHtml;
      if (advFilterSelect) advFilterSelect.innerHTML = filterHtml;
    }
  } catch (err) {
    console.warn("Could not pre-load divisions:", err);
  }
}

// -------------------------------------------------------------
// AUTHENTICATION
// -------------------------------------------------------------
async function handleLogin(e) {
  e.preventDefault();
  const email = document.getElementById("loginEmail").value.trim();
  const password = document.getElementById("loginPassword").value;

  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    const data = await res.json();
    if (!res.ok) {
      showToast(data.message || "Login failed", "error");
      return;
    }

    authToken = data.token;
    currentUser = data.user;
    localStorage.setItem("triad_token", authToken);
    localStorage.setItem("triad_user", JSON.stringify(currentUser));

    showToast(`Welcome back, ${currentUser.name}!`, "success");
    setupUserSession();
  } catch (err) {
    showToast("Server connection error during login", "error");
  }
}

async function handleRegister(e) {
  e.preventDefault();
  const name = document.getElementById("regName").value.trim();
  const email = document.getElementById("regEmail").value.trim();
  const division = document.getElementById("regDivision").value;
  const password = document.getElementById("regPassword").value;

  try {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, division, password })
    });

    const data = await res.json();
    if (!res.ok) {
      showToast(data.message || "Registration failed", "error");
      return;
    }

    showToast("Account created successfully! Signing in...", "success");
    // Auto-login
    document.getElementById("loginEmail").value = email;
    document.getElementById("loginPassword").value = password;
    switchAuthTab("login");
    handleLogin(new Event("submit"));
  } catch (err) {
    showToast("Server connection error during registration", "error");
  }
}

function logout() {
  authToken = null;
  currentUser = null;
  localStorage.removeItem("triad_token");
  localStorage.removeItem("triad_user");
  showToast("Logged out successfully", "info");
  showAuthOverlay();
}

function setupUserSession() {
  hideAuthOverlay();

  document.getElementById("userNameDisplay").textContent = currentUser.name;
  document.getElementById("userAvatar").textContent = currentUser.name.charAt(0).toUpperCase();
  document.getElementById("userRoleBadge").textContent = `${currentUser.division} • ${currentUser.role.replace("_", " ")}`;

  // Show Admin menu item if user is super_admin or division_admin
  const isAdmin = currentUser.role === "super_admin" || currentUser.role === "division_admin";
  document.querySelectorAll(".admin-only").forEach(el => {
    el.style.display = isAdmin ? "flex" : "none";
  });

  document.getElementById("statMyDivision").textContent = currentUser.division;

  loadActiveMetadata();
  loadDocuments();
  loadAccessRequestsCount();
}

// -------------------------------------------------------------
// NAVIGATION
// -------------------------------------------------------------
function navigateTo(view) {
  document.querySelectorAll(".sidebar-menu .menu-item").forEach(item => {
    item.classList.toggle("active", item.getAttribute("data-view") === view);
  });

  document.querySelectorAll(".view-panel").forEach(panel => {
    panel.style.display = "none";
  });

  const pageTitle = document.getElementById("pageTitle");
  const pageSubtitle = document.getElementById("pageSubtitle");

  if (view === "dashboard") {
    document.getElementById("viewDashboard").style.display = "block";
    pageTitle.textContent = "Document Hub";
    pageSubtitle.textContent = "Browse and manage division documents with dynamic metadata";
    loadDocuments();
  } else if (view === "search") {
    document.getElementById("viewSearch").style.display = "block";
    pageTitle.textContent = "Advanced Search";
    pageSubtitle.textContent = "Search across document titles, custom metadata, and OCR-extracted text";
  } else if (view === "requests") {
    document.getElementById("viewRequests").style.display = "block";
    pageTitle.textContent = "Access Requests Inbox";
    pageSubtitle.textContent = "Manage cross-division document access requests and approvals";
    loadAccessRequests();
  } else if (view === "admin") {
    document.getElementById("viewAdmin").style.display = "block";
    pageTitle.textContent = "Custom Metadata Settings";
    pageSubtitle.textContent = "Configure and manage extensible dynamic fields for documents";
    loadMetadataFields();
  }
}

// -------------------------------------------------------------
// DYNAMIC METADATA
// -------------------------------------------------------------
async function loadActiveMetadata() {
  try {
    const res = await fetch(`${API_BASE}/metadata/active`, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (res.ok) {
      const data = await res.json();
      activeMetadataFields = data.metadata_fields || [];
      document.getElementById("statActiveMeta").textContent = activeMetadataFields.length;
      populateReportTypeFilter();
    }
  } catch (err) {
    console.error("Failed to load active metadata:", err);
  }
}

function populateReportTypeFilter() {
  // Check if there is a 'Report Type' field
  const reportTypeField = activeMetadataFields.find(f => f.field_name.toLowerCase() === "report type");
  const select = document.getElementById("reportTypeFilter");
  const advSelect = document.getElementById("advReportTypeFilter");

  let html = '<option value="">All Report Types</option>';
  if (reportTypeField && reportTypeField.options) {
    reportTypeField.options.forEach(opt => {
      html += `<option value="${opt}">${opt}</option>`;
    });
  } else {
    // Standard default options
    ["Financial", "Audit", "Operational", "Technical", "Confidential"].forEach(opt => {
      html += `<option value="${opt}">${opt}</option>`;
    });
  }

  if (select) select.innerHTML = html;
  if (advSelect) advSelect.innerHTML = html;
}

// -------------------------------------------------------------
// VIEW 1: DOCUMENT HUB & LISTING
// -------------------------------------------------------------
async function loadDocuments() {
  const tbody = document.getElementById("documentsTableBody");
  tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Loading documents...</td></tr>';

  const divFilter = document.getElementById("divisionFilter").value;
  const reportFilter = document.getElementById("reportTypeFilter").value;

  let queryUrl = `${API_BASE}/documents?`;
  if (divFilter) queryUrl += `division=${encodeURIComponent(divFilter)}&`;
  if (reportFilter) queryUrl += `Report Type=${encodeURIComponent(reportFilter)}&`;

  try {
    const res = await fetch(queryUrl, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });

    if (!res.ok) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--danger);">Failed to load documents</td></tr>';
      return;
    }

    const data = await res.json();
    cachedDocuments = data.documents || [];
    document.getElementById("statTotalDocs").textContent = cachedDocuments.length;

    renderDocumentsTable(cachedDocuments);
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--danger);">Server connection error</td></tr>';
  }
}

function renderDocumentsTable(docs) {
  const tbody = document.getElementById("documentsTableBody");
  if (!docs || docs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 2rem;">No documents found matching the filter criteria.</td></tr>';
    return;
  }

  tbody.innerHTML = docs.map(doc => {
    // Render dynamic metadata badges
    const metaBadges = Object.entries(doc.metadata || {})
      .map(([k, v]) => `<span class="badge badge-neutral">${escapeHtml(k)}: <strong>${escapeHtml(String(v))}</strong></span>`)
      .join(" ");

    const hasAccess = currentUser.role === "super_admin" || currentUser.division === doc.division;
    const dateFormatted = doc.created_at ? new Date(doc.created_at).toLocaleDateString() : "-";
    const ocrBadge = doc.has_ocr 
      ? '<span class="badge badge-success"><i class="fa-solid fa-check"></i> OCR Ready</span>'
      : '<span class="badge badge-warning"><i class="fa-solid fa-hourglass-half"></i> Processing</span>';

    return `
      <tr>
        <td>
          <div style="font-weight: 700; color: var(--text-main); font-size: 0.95rem;">
            <i class="fa-regular fa-file-pdf" style="color: #ef4444; margin-right: 0.5rem;"></i>
            ${escapeHtml(doc.title || doc.original_name)}
          </div>
          <div style="font-size: 0.78rem; color: var(--text-muted);">${escapeHtml(doc.original_name)}</div>
        </td>
        <td>
          <span class="badge badge-primary">${escapeHtml(doc.division)}</span>
        </td>
        <td>
          <div style="display: flex; gap: 0.35rem; flex-wrap: wrap;">
            ${metaBadges || '<span style="color: var(--text-muted); font-size: 0.8rem;">None</span>'}
          </div>
        </td>
        <td>${ocrBadge}</td>
        <td style="color: var(--text-muted); font-size: 0.85rem;">${dateFormatted}</td>
        <td>
          <div style="display: flex; gap: 0.4rem;">
            <button class="btn btn-secondary btn-sm" onclick="openDocDetails('${doc.id}')" title="Inspect Metadata & OCR">
              <i class="fa-solid fa-eye"></i> View
            </button>
            <button class="btn btn-primary btn-sm" onclick="downloadDocument('${doc.id}')" title="Download Document">
              <i class="fa-solid fa-download"></i> Download
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

function filterDocumentsTable() {
  const query = document.getElementById("docSearchFilter").value.toLowerCase();
  if (!query) {
    renderDocumentsTable(cachedDocuments);
    return;
  }
  const filtered = cachedDocuments.filter(d => 
    (d.title && d.title.toLowerCase().includes(query)) ||
    (d.original_name && d.original_name.toLowerCase().includes(query))
  );
  renderDocumentsTable(filtered);
}

// -------------------------------------------------------------
// DOCUMENT UPLOAD
// -------------------------------------------------------------
function openUploadModal() {
  document.getElementById("uploadDocForm").reset();
  document.getElementById("uploadDivisionDisplay").value = currentUser.division;

  // Build dynamic metadata fields
  const container = document.getElementById("dynamicFieldsContainer");
  if (!activeMetadataFields || activeMetadataFields.length === 0) {
    // Provide default fallback fields if none configured
    container.innerHTML = `
      <div class="form-group">
        <label>Report Type</label>
        <select class="form-control dynamic-meta-input" data-key="Report Type">
          <option value="Financial">Financial</option>
          <option value="Audit">Audit</option>
          <option value="Operational">Operational</option>
          <option value="Technical">Technical</option>
        </select>
      </div>
      <div class="form-group">
        <label>Fiscal Year</label>
        <input type="number" class="form-control dynamic-meta-input" data-key="Year" value="2026">
      </div>
    `;
  } else {
    container.innerHTML = activeMetadataFields.map(f => {
      let inputHtml = "";
      if (f.field_type === "dropdown" && f.options && f.options.length > 0) {
        inputHtml = `
          <select class="form-control dynamic-meta-input" data-key="${escapeHtml(f.field_name)}" ${f.required ? 'required' : ''}>
            <option value="">Select ${escapeHtml(f.field_name)}...</option>
            ${f.options.map(o => `<option value="${escapeHtml(o)}">${escapeHtml(o)}</option>`).join("")}
          </select>
        `;
      } else if (f.field_type === "number") {
        inputHtml = `<input type="number" class="form-control dynamic-meta-input" data-key="${escapeHtml(f.field_name)}" ${f.required ? 'required' : ''}>`;
      } else if (f.field_type === "date") {
        inputHtml = `<input type="date" class="form-control dynamic-meta-input" data-key="${escapeHtml(f.field_name)}" ${f.required ? 'required' : ''}>`;
      } else {
        inputHtml = `<input type="text" class="form-control dynamic-meta-input" data-key="${escapeHtml(f.field_name)}" placeholder="Value..." ${f.required ? 'required' : ''}>`;
      }

      return `
        <div class="form-group">
          <label>${escapeHtml(f.field_name)} ${f.required ? '<span style="color:red">*</span>' : ''}</label>
          ${inputHtml}
        </div>
      `;
    }).join("");
  }

  document.getElementById("uploadModal").style.display = "flex";
}

async function handleDocumentUpload(e) {
  e.preventDefault();
  const fileInput = document.getElementById("uploadFile");
  if (!fileInput.files || fileInput.files.length === 0) {
    showToast("Please select a file to upload", "error");
    return;
  }

  const file = fileInput.files[0];
  const title = document.getElementById("uploadTitle").value.trim();

  // Collect dynamic metadata values
  const metadataObj = {};
  document.querySelectorAll(".dynamic-meta-input").forEach(inp => {
    const key = inp.getAttribute("data-key");
    const val = inp.value.trim();
    if (val) {
      metadataObj[key] = isNaN(val) ? val : Number(val);
    }
  });

  const formData = new FormData();
  formData.append("file", file);
  formData.append("title", title);
  formData.append("metadata", JSON.stringify(metadataObj));

  const btn = document.getElementById("btnUploadSubmit");
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing OCR...';

  try {
    const res = await fetch(`${API_BASE}/documents/upload`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${authToken}` },
      body: formData
    });

    const data = await res.json();
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-check"></i> Upload & Process OCR';

    if (!res.ok) {
      showToast(data.message || "Upload failed", "error");
      return;
    }

    closeModal("uploadModal");
    showToast(`Document uploaded successfully! ${data.has_ocr ? '(OCR extracted)' : ''}`, "success");
    loadDocuments();
  } catch (err) {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-check"></i> Upload & Process OCR';
    showToast("Server error during upload", "error");
  }
}

// -------------------------------------------------------------
// DOCUMENT DETAILS, PREVIEW & DOWNLOAD
// -------------------------------------------------------------
async function openDocDetails(docId) {
  try {
    const res = await fetch(`${API_BASE}/documents/${docId}`, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });

    if (res.status === 403) {
      // Access denied - Show Request Access dialog directly
      currentDocInModal = { id: docId, isDenied: true };
      showRequestAccessPrompt(docId);
      return;
    }

    if (!res.ok) {
      showToast("Document not found or error", "error");
      return;
    }

    const data = await res.json();
    currentDocInModal = data.document;

    document.getElementById("modalDocTitle").textContent = currentDocInModal.title;

    // Attributes Table
    document.getElementById("docMetaAttributes").innerHTML = `
      <tr><th style="width: 140px;">Title</th><td><strong>${escapeHtml(currentDocInModal.title)}</strong></td></tr>
      <tr><th>Original File</th><td>${escapeHtml(currentDocInModal.original_name)} (${(currentDocInModal.size / 1024).toFixed(1)} KB)</td></tr>
      <tr><th>Division</th><td><span class="badge badge-primary">${escapeHtml(currentDocInModal.division)}</span></td></tr>
      <tr><th>Content Type</th><td>${escapeHtml(currentDocInModal.content_type || 'application/pdf')}</td></tr>
      <tr><th>Uploaded At</th><td>${currentDocInModal.created_at ? new Date(currentDocInModal.created_at).toLocaleString() : '-'}</td></tr>
    `;

    // Custom metadata tags
    const metaList = document.getElementById("docCustomMetaList");
    if (currentDocInModal.metadata && Object.keys(currentDocInModal.metadata).length > 0) {
      metaList.innerHTML = Object.entries(currentDocInModal.metadata).map(([k, v]) => `
        <span class="badge badge-neutral" style="font-size: 0.85rem; padding: 0.4rem 0.8rem;">
          ${escapeHtml(k)}: <strong>${escapeHtml(String(v))}</strong>
        </span>
      `).join("");
    } else {
      metaList.innerHTML = '<span style="color: var(--text-muted);">No custom metadata attributes recorded.</span>';
    }

    // Load OCR
    loadDocOcrText(docId);

    // Set preview frame
    document.getElementById("docPreviewFrame").src = `${API_BASE}/documents/${docId}/preview`;

    // Footer actions
    const footer = document.getElementById("docDetailsFooter");
    footer.innerHTML = `
      <button class="btn btn-secondary" onclick="closeModal('docDetailsModal')">Close</button>
      <button class="btn btn-primary" onclick="downloadDocument('${docId}')">
        <i class="fa-solid fa-download"></i> Download Document
      </button>
    `;

    switchDocDetailTab("meta");
    document.getElementById("docDetailsModal").style.display = "flex";
  } catch (err) {
    showToast("Error retrieving document details", "error");
  }
}

async function loadDocOcrText(docId) {
  const ocrBox = document.getElementById("docOcrContent");
  ocrBox.textContent = "Loading OCR extracted text...";
  try {
    const res = await fetch(`${API_BASE}/documents/${docId}/ocr`, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (res.ok) {
      const data = await res.json();
      ocrBox.textContent = data.extracted_text || "(No text content found in document)";
    } else {
      ocrBox.textContent = "(OCR text unavailable or access denied)";
    }
  } catch (err) {
    ocrBox.textContent = "(Error loading OCR content)";
  }
}

function switchDocDetailTab(tab) {
  document.getElementById("tabDocMeta").classList.toggle("active", tab === "meta");
  document.getElementById("tabDocOcr").classList.toggle("active", tab === "ocr");
  document.getElementById("tabDocPreview").classList.toggle("active", tab === "preview");

  document.getElementById("docDetailMetaSection").style.display = tab === "meta" ? "block" : "none";
  document.getElementById("docDetailOcrSection").style.display = tab === "ocr" ? "block" : "none";
  document.getElementById("docDetailPreviewSection").style.display = tab === "preview" ? "block" : "none";
}

function copyOcrText() {
  const text = document.getElementById("docOcrContent").textContent;
  navigator.clipboard.writeText(text);
  showToast("OCR text copied to clipboard!", "success");
}

function downloadDocument(docId) {
  // Direct authorized download via browser stream
  fetch(`${API_BASE}/documents/${docId}/download`, {
    headers: { "Authorization": `Bearer ${authToken}` }
  })
  .then(res => {
    if (res.status === 403) {
      showToast("Access Denied: You do not belong to this document's division. Please request cross-division access.", "error");
      showRequestAccessPrompt(docId);
      return null;
    }
    if (!res.ok) {
      showToast("Download failed", "error");
      return null;
    }
    const disposition = res.headers.get("Content-Disposition");
    let filename = "document.pdf";
    if (disposition && disposition.includes("filename=")) {
      filename = disposition.split("filename=")[1].replace(/"/g, "").trim();
    }
    return res.blob().then(blob => ({ blob, filename }));
  })
  .then(fileData => {
    if (!fileData) return;
    const url = window.URL.createObjectURL(fileData.blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = fileData.filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    showToast(`Downloading ${fileData.filename}...`, "success");
  })
  .catch(err => {
    showToast("Error downloading document", "error");
  });
}

function showRequestAccessPrompt(docId) {
  const footer = document.getElementById("docDetailsFooter");
  document.getElementById("modalDocTitle").textContent = "Cross-Division Access Required";
  document.getElementById("docMetaAttributes").innerHTML = `
    <tr><td colspan="2" style="padding: 1.5rem; text-align: center; color: var(--text-muted);">
      <div style="font-size: 2.5rem; color: #f59e0b; margin-bottom: 0.5rem;"><i class="fa-solid fa-lock"></i></div>
      <h3 style="font-size: 1.1rem; color: var(--text-main); margin-bottom: 0.5rem;">Access Restricted by RBAC Policy</h3>
      <p>This document belongs to another division. To view, download, or inspect its contents, you must request cross-division authorization.</p>
    </td></tr>
  `;
  document.getElementById("docCustomMetaList").innerHTML = "";
  switchDocDetailTab("meta");

  footer.innerHTML = `
    <button class="btn btn-secondary" onclick="closeModal('docDetailsModal')">Cancel</button>
    <button class="btn btn-primary" onclick="submitAccessRequest('${docId}')">
      <i class="fa-solid fa-key"></i> Request Access
    </button>
  `;
  document.getElementById("docDetailsModal").style.display = "flex";
}

// -------------------------------------------------------------
// VIEW 2: ADVANCED SEARCH
// -------------------------------------------------------------
async function handleAdvancedSearch(e) {
  e.preventDefault();
  const query = document.getElementById("advSearchInput").value.trim();
  const division = document.getElementById("advDivisionFilter").value;
  const reportType = document.getElementById("advReportTypeFilter").value;

  if (!query && !division && !reportType) {
    showToast("Enter a search term or filter", "info");
    return;
  }

  const tbody = document.getElementById("searchResultsBody");
  tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Searching across documents, metadata & OCR...</td></tr>';

  let searchUrl = `${API_BASE}/search?q=${encodeURIComponent(query)}&`;
  if (division) searchUrl += `division=${encodeURIComponent(division)}&`;
  if (reportType) searchUrl += `Report Type=${encodeURIComponent(reportType)}&`;

  try {
    const res = await fetch(searchUrl, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });

    if (!res.ok) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--danger);">Search query failed</td></tr>';
      return;
    }

    const data = await res.json();
    const results = data.results || data.documents || [];

    document.getElementById("searchResultsHeader").textContent = `Search Results (${results.length} found)`;

    if (results.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 2rem;">No matching documents found.</td></tr>';
      return;
    }

    tbody.innerHTML = results.map(doc => {
      const matchBadges = (doc.matched_in || ["title"])
        .map(m => `<span class="badge badge-warning">${escapeHtml(m)}</span>`)
        .join(" ");

      const snippet = doc.match_snippet || doc.ocr_snippet || "Match found in document";

      return `
        <tr>
          <td>
            <div style="font-weight: 700; color: var(--text-main); font-size: 0.95rem;">
              <i class="fa-regular fa-file-pdf" style="color: #ef4444; margin-right: 0.5rem;"></i>
              ${escapeHtml(doc.title || doc.original_name)}
            </div>
            <div style="font-size: 0.78rem; color: var(--text-muted);">${escapeHtml(doc.original_name)}</div>
          </td>
          <td><span class="badge badge-primary">${escapeHtml(doc.division)}</span></td>
          <td>${matchBadges}</td>
          <td style="font-size: 0.82rem; color: var(--text-muted); max-width: 320px;">
            <code>${escapeHtml(snippet)}</code>
          </td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="openDocDetails('${doc.id}')">
              <i class="fa-solid fa-eye"></i> View
            </button>
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--danger);">Search error</td></tr>';
  }
}

// -------------------------------------------------------------
// VIEW 3: ACCESS REQUESTS INBOX
// -------------------------------------------------------------
async function submitAccessRequest(docId) {
  try {
    const res = await fetch(`${API_BASE}/access/request`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ document_id: docId })
    });

    const data = await res.json();
    if (!res.ok) {
      showToast(data.message || "Failed to submit request", "error");
      return;
    }

    closeModal("docDetailsModal");
    showToast("Access request submitted successfully! An administrator will review it.", "success");
    loadAccessRequests();
  } catch (err) {
    showToast("Server error during access request", "error");
  }
}

async function loadAccessRequestsCount() {
  try {
    const res = await fetch(`${API_BASE}/access/requests?status=pending`, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (res.ok) {
      const data = await res.json();
      const count = data.count || 0;
      document.getElementById("statPendingReqs").textContent = count;
      const badge = document.getElementById("pendingBadge");
      if (count > 0) {
        badge.textContent = count;
        badge.style.display = "inline-block";
      } else {
        badge.style.display = "none";
      }
    }
  } catch (e) {}
}

function switchRequestTab(tab) {
  currentRequestTab = tab;
  document.getElementById("tabIncoming").classList.toggle("active", tab === "incoming");
  document.getElementById("tabOutgoing").classList.toggle("active", tab === "outgoing");
  loadAccessRequests();
}

async function loadAccessRequests() {
  const tbody = document.getElementById("requestsTableBody");
  tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Loading requests...</td></tr>';

  try {
    const res = await fetch(`${API_BASE}/access/requests`, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });

    if (!res.ok) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--danger);">Failed to load requests</td></tr>';
      return;
    }

    const data = await res.json();
    const allRequests = data.requests || [];

    // Filter incoming vs outgoing
    let incoming = [];
    let outgoing = [];

    allRequests.forEach(r => {
      if (r.user_id === currentUser.id) {
        outgoing.push(r);
      }
      if (currentUser.role === "super_admin" || (currentUser.role === "division_admin" && r.document_division === currentUser.division)) {
        if (r.user_id !== currentUser.id) {
          incoming.push(r);
        }
      }
    });

    document.getElementById("incomingCount").textContent = incoming.length;
    document.getElementById("outgoingCount").textContent = outgoing.length;

    const displayList = currentRequestTab === "incoming" ? incoming : outgoing;

    if (displayList.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 2rem;">No ${currentRequestTab} requests found.</td></tr>`;
      return;
    }

    tbody.innerHTML = displayList.map(req => {
      let statusBadge = "";
      if (req.status === "approved") {
        statusBadge = '<span class="badge badge-success"><i class="fa-solid fa-check"></i> Approved</span>';
      } else if (req.status === "rejected") {
        statusBadge = '<span class="badge badge-danger"><i class="fa-solid fa-xmark"></i> Rejected</span>';
      } else {
        statusBadge = '<span class="badge badge-warning"><i class="fa-solid fa-clock"></i> Pending</span>';
      }

      let actionsHtml = "-";
      if (currentRequestTab === "incoming" && req.status === "pending") {
        actionsHtml = `
          <div style="display: flex; gap: 0.4rem;">
            <button class="btn btn-success btn-sm" onclick="handleApproveRequest('${req.id}')">
              <i class="fa-solid fa-check"></i> Approve
            </button>
            <button class="btn btn-danger btn-sm" onclick="handleRejectRequest('${req.id}')">
              <i class="fa-solid fa-xmark"></i> Reject
            </button>
          </div>
        `;
      }

      return `
        <tr>
          <td><strong>${escapeHtml(req.document_title || 'Document')}</strong></td>
          <td>${escapeHtml(req.requester_name || req.requester_email || 'User')}</td>
          <td><span class="badge badge-neutral">${escapeHtml(req.requester_division)}</span></td>
          <td><span class="badge badge-primary">${escapeHtml(req.document_division)}</span></td>
          <td>${statusBadge}</td>
          <td style="color: var(--text-muted); font-size: 0.85rem;">${req.created_at ? new Date(req.created_at).toLocaleDateString() : '-'}</td>
          <td>${actionsHtml}</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--danger);">Server error</td></tr>';
  }
}

async function handleApproveRequest(requestId) {
  try {
    const res = await fetch(`${API_BASE}/access/approve`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ request_id: requestId })
    });

    const data = await res.json();
    if (!res.ok) {
      showToast(data.message || "Failed to approve request", "error");
      return;
    }

    showToast("Access request approved! Requester now has document download permissions.", "success");
    loadAccessRequests();
    loadAccessRequestsCount();
  } catch (err) {
    showToast("Approval error", "error");
  }
}

async function handleRejectRequest(requestId) {
  try {
    const res = await fetch(`${API_BASE}/access/reject`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ request_id: requestId })
    });

    const data = await res.json();
    if (!res.ok) {
      showToast(data.message || "Failed to reject request", "error");
      return;
    }

    showToast("Access request rejected.", "info");
    loadAccessRequests();
    loadAccessRequestsCount();
  } catch (err) {
    showToast("Rejection error", "error");
  }
}

// -------------------------------------------------------------
// VIEW 4: ADMIN / CUSTOM METADATA SETTINGS
// -------------------------------------------------------------
async function loadMetadataFields() {
  const tbody = document.getElementById("metadataTableBody");
  tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Loading custom fields...</td></tr>';

  try {
    const res = await fetch(`${API_BASE}/metadata`, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });

    if (!res.ok) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--danger);">Failed to load metadata fields</td></tr>';
      return;
    }

    const data = await res.json();
    const fields = data.metadata_fields || [];

    if (fields.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 2rem;">No custom metadata fields defined. Click "Add New Field" above.</td></tr>';
      return;
    }

    tbody.innerHTML = fields.map(f => {
      const optionsStr = (f.options && f.options.length > 0) ? f.options.join(", ") : "-";
      const statusBadge = f.active 
        ? '<span class="badge badge-success">Active</span>'
        : '<span class="badge badge-neutral">Inactive</span>';

      const actionHtml = f.active 
        ? `<button class="btn btn-secondary btn-sm" onclick="deactivateMetadataField('${f.id}')"><i class="fa-solid fa-ban"></i> Deactivate</button>`
        : `<span style="color: var(--text-muted); font-size: 0.8rem;">Deactivated</span>`;

      return `
        <tr>
          <td><strong>${escapeHtml(f.field_name)}</strong></td>
          <td><span class="badge badge-primary">${escapeHtml(f.field_type)}</span></td>
          <td style="max-width: 250px; font-size: 0.85rem; color: var(--text-muted);">${escapeHtml(optionsStr)}</td>
          <td>${f.required ? '<span class="badge badge-warning">Required</span>' : '<span style="color: var(--text-muted);">Optional</span>'}</td>
          <td>${statusBadge}</td>
          <td>${actionHtml}</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--danger);">Error loading metadata fields</td></tr>';
  }
}

function openAddMetadataModal() {
  document.getElementById("addMetadataForm").reset();
  toggleDropdownOptionsInput("text");
  document.getElementById("addMetadataModal").style.display = "flex";
}

function toggleDropdownOptionsInput(type) {
  document.getElementById("metaOptionsGroup").style.display = (type === "dropdown") ? "block" : "none";
}

async function handleCreateMetadata(e) {
  e.preventDefault();
  const field_name = document.getElementById("metaFieldName").value.trim();
  const field_type = document.getElementById("metaFieldType").value;
  const optionsRaw = document.getElementById("metaOptionsInput").value.trim();
  const required = document.getElementById("metaRequired").checked;

  let options = [];
  if (field_type === "dropdown") {
    if (!optionsRaw) {
      showToast("Please provide options for dropdown field", "error");
      return;
    }
    options = optionsRaw.split(",").map(o => o.trim()).filter(Boolean);
  }

  try {
    const res = await fetch(`${API_BASE}/metadata`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ field_name, field_type, options, required })
    });

    const data = await res.json();
    if (!res.ok) {
      showToast(data.message || "Failed to create field", "error");
      return;
    }

    closeModal("addMetadataModal");
    showToast(`Metadata field '${field_name}' created successfully!`, "success");
    loadMetadataFields();
    loadActiveMetadata();
  } catch (err) {
    showToast("Error creating metadata field", "error");
  }
}

async function deactivateMetadataField(id) {
  if (!confirm("Are you sure you want to deactivate this metadata field?")) return;
  try {
    const res = await fetch(`${API_BASE}/metadata/${id}`, {
      method: "DELETE",
      headers: { "Authorization": `Bearer ${authToken}` }
    });

    if (res.ok) {
      showToast("Metadata field deactivated", "info");
      loadMetadataFields();
      loadActiveMetadata();
    }
  } catch (e) {
    showToast("Deactivation failed", "error");
  }
}

// -------------------------------------------------------------
// UTILITIES
// -------------------------------------------------------------
function closeModal(id) {
  document.getElementById(id).style.display = "none";
}

function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;

  let icon = "fa-info-circle";
  if (type === "success") icon = "fa-circle-check";
  if (type === "error") icon = "fa-triangle-exclamation";

  toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    toast.style.transition = "all 0.3s";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function escapeHtml(text) {
  if (text === null || text === undefined) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
