/**
 * RAG System — Document Management Logic
 * Handles: drag-and-drop upload, file list, delete, and processing.
 */

const API_BASE = '/api';

const uploadZone = document.getElementById('upload-zone');
const fileInput = document.getElementById('file-input');
const uploadProgress = document.getElementById('upload-progress');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const processBtn = document.getElementById('process-btn');
const refreshBtn = document.getElementById('refresh-btn');
const docsTbody = document.getElementById('docs-tbody');
const deleteModal = document.getElementById('delete-modal');
const deleteFileName = document.getElementById('delete-file-name');
const cancelDelete = document.getElementById('cancel-delete');
const confirmDelete = document.getElementById('confirm-delete');

let pendingDeleteFile = null;

// ── Initialize ──

document.addEventListener('DOMContentLoaded', () => {
    setupUploadZone();
    setupButtons();
    setupModal();
    setupSidebarToggle();
    loadDocuments();
});

// ── Upload Zone ──

function setupUploadZone() {
    // Click to browse
    uploadZone.addEventListener('click', () => fileInput.click());

    // File input change
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            uploadFiles(fileInput.files);
        }
    });

    // Drag & drop
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('drag-over');
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('drag-over');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('drag-over');
        if (e.dataTransfer.files.length > 0) {
            uploadFiles(e.dataTransfer.files);
        }
    });
}

// ── File Upload ──

async function uploadFiles(files) {
    const formData = new FormData();
    for (const file of files) {
        formData.append('files', file);
    }

    // Show progress
    uploadProgress.hidden = false;
    uploadProgress.style.display = 'block';
    progressFill.style.width = '0%';
    progressText.textContent = `Uploading ${files.length} file(s)...`;

    try {
        // Simulate upload progress (real progress would require XMLHttpRequest)
        progressFill.style.width = '30%';
        progressText.textContent = 'Uploading and processing...';

        const response = await fetch(`${API_BASE}/ingest`, {
            method: 'POST',
            body: formData,
        });

        progressFill.style.width = '100%';

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Upload failed: ${response.status}`);
        }

        const data = await response.json();
        progressText.textContent = `✓ Processed ${data.processed} file(s), created ${data.chunks} chunks`;

        if (data.errors && data.errors.length > 0) {
            progressText.textContent += ` (${data.errors.length} error(s))`;
        }

        // Refresh document list
        setTimeout(() => {
            loadDocuments();
            loadSidebarStats();
        }, 500);

    } catch (error) {
        progressFill.style.width = '100%';
        progressFill.style.background = 'var(--danger)';
        progressText.textContent = `⚠️ Error: ${error.message}`;
    }

    // Reset file input
    fileInput.value = '';

    // Hide progress after 5s
    setTimeout(() => {
        uploadProgress.hidden = true;
        uploadProgress.style.display = 'none';
        progressFill.style.background = '';
    }, 5000);
}

// ── Buttons ──

function setupButtons() {
    processBtn.addEventListener('click', async () => {
        processBtn.disabled = true;
        processBtn.textContent = '⏳ Processing...';

        try {
            const response = await fetch(`${API_BASE}/ingest`, {
                method: 'POST',
            });

            if (!response.ok) throw new Error(`Failed: ${response.status}`);

            const data = await response.json();
            processBtn.textContent = `✓ ${data.processed} processed, ${data.chunks} chunks`;

            loadDocuments();
            loadSidebarStats();
        } catch (error) {
            processBtn.textContent = `⚠️ Error`;
        }

        setTimeout(() => {
            processBtn.disabled = false;
            processBtn.textContent = '⚡ Process All Pending';
        }, 3000);
    });

    refreshBtn.addEventListener('click', () => {
        loadDocuments();
        loadSidebarStats();
    });
}

// ── Load Documents ──

async function loadDocuments() {
    try {
        const response = await fetch(`${API_BASE}/documents`);
        if (!response.ok) throw new Error(`Failed: ${response.status}`);

        const documents = await response.json();
        renderDocumentsTable(documents);
    } catch (error) {
        docsTbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="6">
                    <div class="empty-state">
                        <span class="empty-icon">⚠️</span>
                        <p>Could not load documents. Is the server running?</p>
                    </div>
                </td>
            </tr>
        `;
    }
}

function renderDocumentsTable(documents) {
    if (!documents || documents.length === 0) {
        docsTbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="6">
                    <div class="empty-state">
                        <span class="empty-icon">📭</span>
                        <p>No documents yet. Upload some files to get started.</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    docsTbody.innerHTML = documents.map(doc => {
        const sizeStr = formatFileSize(doc.size_bytes);
        const typeIcon = getTypeIcon(doc.extension);
        const statusClass = doc.ingested ? 'indexed' : 'pending';
        const statusText = doc.ingested ? '✓ Indexed' : '⏳ Pending';

        return `
            <tr>
                <td class="file-name">${typeIcon} ${escapeHtml(doc.name)}</td>
                <td><span class="type-badge">${doc.extension}</span></td>
                <td>${sizeStr}</td>
                <td>${doc.chunk_count || '—'}</td>
                <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                <td>
                    <button class="delete-btn" onclick="showDeleteModal('${escapeHtml(doc.name)}')">
                        🗑️ Delete
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

// ── Delete Modal ──

function setupModal() {
    deleteModal.hidden = true;
    deleteModal.style.display = 'none';

    cancelDelete.addEventListener('click', hideDeleteModal);
    confirmDelete.addEventListener('click', performDelete);

    deleteModal.addEventListener('click', (e) => {
        if (e.target === deleteModal) hideDeleteModal();
    });
}

function showDeleteModal(fileName) {
    pendingDeleteFile = fileName;
    deleteFileName.textContent = fileName;
    deleteModal.hidden = false;
    deleteModal.style.display = 'flex';
}

function hideDeleteModal() {
    deleteModal.hidden = true;
    deleteModal.style.display = 'none';
    pendingDeleteFile = null;
}

window.showDeleteModal = showDeleteModal;

async function performDelete() {
    if (!pendingDeleteFile) return;

    const fileName = pendingDeleteFile;
    hideDeleteModal();

    try {
        const response = await fetch(`${API_BASE}/documents/${encodeURIComponent(fileName)}`, {
            method: 'DELETE',
        });

        if (!response.ok) throw new Error(`Delete failed: ${response.status}`);

        loadDocuments();
        loadSidebarStats();
    } catch (error) {
        alert(`Failed to delete: ${error.message}`);
    }
}

// ── Sidebar Stats ──

async function loadSidebarStats() {
    try {
        const response = await fetch(`${API_BASE}/stats`);
        if (response.ok) {
            const stats = await response.json();
            const statDocs = document.getElementById('stat-docs');
            const statChunks = document.getElementById('stat-chunks');
            if (statDocs) statDocs.textContent = stats.ingested_files;
            if (statChunks) statChunks.textContent = stats.total_chunks;
        }
    } catch (e) {
        // Silent fail
    }
}

function setupSidebarToggle() {
    const toggle = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    if (toggle && sidebar) {
        toggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }
}

// ── Utilities ──

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function getTypeIcon(ext) {
    const icons = {
        '.pdf': '📕',
        '.docx': '📘',
        '.xlsx': '📗',
        '.png': '🖼️',
        '.jpg': '🖼️',
        '.jpeg': '🖼️',
        '.txt': '📝',
        '.md': '📝',
        '.eml': '✉️',
    };
    return icons[ext] || '📄';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
