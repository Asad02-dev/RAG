/**
 * Graph Agent POC — Chat Interface Logic
 * Sends messages to POST /api/agent/chat with a session id,
 * so the agent keeps the conversation history.
 */

const API_BASE = '/api';
const messagesContainer = document.getElementById('messages-container');
const queryInput = document.getElementById('query-input');
const sendBtn = document.getElementById('send-btn');
const clearBtn = document.getElementById('clear-chat');
const welcomeMessage = document.getElementById('welcome-message');
const sessionIdEl = document.getElementById('session-id');
const jsonFileInput = document.getElementById('json-file-input');
const ingestJsonBtn = document.getElementById('ingest-json-btn');
const ingestStatus = document.getElementById('ingest-status');

let sessionId = newSessionId();

// ── Initialize ──

document.addEventListener('DOMContentLoaded', () => {
    sessionIdEl.textContent = sessionId.slice(0, 8);
    setupInputHandlers();
    setupSidebarToggle();
    queryInput.focus();
});

// ── Session ──

function newSessionId() {
    return crypto.randomUUID();
}

// ── Input Handlers ──

function setupInputHandlers() {
    queryInput.addEventListener('input', () => {
        // Auto-resize textarea
        queryInput.style.height = 'auto';
        queryInput.style.height = Math.min(queryInput.scrollHeight, 150) + 'px';
        // Enable/disable send button
        sendBtn.disabled = !queryInput.value.trim();
    });

    queryInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (queryInput.value.trim()) {
                sendMessage();
            }
        }
    });

    sendBtn.addEventListener('click', () => {
        if (queryInput.value.trim()) {
            sendMessage();
        }
    });

    clearBtn.addEventListener('click', newSession);

    ingestJsonBtn.addEventListener('click', () => jsonFileInput.click());
    jsonFileInput.addEventListener('change', ingestJsonFiles);
}

// ── Ingest JSON into Neo4j ──

async function ingestJsonFiles() {
    const files = Array.from(jsonFileInput.files);
    if (!files.length) return;

    ingestJsonBtn.disabled = true;
    const lines = [];

    // One file at a time, so each result can be shown as it finishes
    for (const file of files) {
        lines.push(`⏳ ${escapeHtml(file.name)}: ingesting...`);
        ingestStatus.innerHTML = lines.join('<br>');

        let line;
        try {
            const data = JSON.parse(await file.text());

            const response = await fetch(`${API_BASE}/neo4j/ingest`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ data }),
            });

            const result = await response.json().catch(() => ({}));
            if (!response.ok) {
                const detail = typeof result.detail === 'string' ? result.detail : `Server error: ${response.status}`;
                throw new Error(detail);
            }

            line = `✅ ${escapeHtml(file.name)}: ${result.triplets_created} triplets, ` +
                   `${result.standalone_nodes_created} standalone nodes`;
        } catch (error) {
            line = `⚠️ ${escapeHtml(file.name)}: ${escapeHtml(error.message)}`;
        }

        lines[lines.length - 1] = line;
        ingestStatus.innerHTML = lines.join('<br>');
    }

    // Reset so the same file can be chosen again
    jsonFileInput.value = '';
    ingestJsonBtn.disabled = false;
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

// ── Send Message ──

async function sendMessage() {
    const message = queryInput.value.trim();
    if (!message) return;

    // Hide welcome message
    if (welcomeMessage) {
        welcomeMessage.style.display = 'none';
    }

    // Add user message
    addMessage('user', message);

    // Clear input
    queryInput.value = '';
    queryInput.style.height = 'auto';
    sendBtn.disabled = true;

    // Show typing indicator
    const typingEl = addTypingIndicator();

    try {
        const response = await fetch(`${API_BASE}/agent/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, message }),
        });

        // Remove typing indicator
        typingEl.remove();

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Server error: ${response.status}`);
        }

        const data = await response.json();
        addMessage('assistant', data.response);

    } catch (error) {
        typingEl.remove();
        addMessage('assistant', `⚠️ Error: ${error.message}. Make sure the server is running.`);
    }

    queryInput.focus();
}

// ── New Session ──

function newSession() {
    sessionId = newSessionId();
    sessionIdEl.textContent = sessionId.slice(0, 8);
    messagesContainer.innerHTML = '';
    if (welcomeMessage) {
        messagesContainer.appendChild(welcomeMessage);
        welcomeMessage.style.display = '';
    }
    queryInput.focus();
}

// ── Message Rendering ──

function addMessage(role, content) {
    const messageEl = document.createElement('div');
    messageEl.className = `message ${role}`;

    const avatar = role === 'user' ? '👤' : '🤖';
    const renderedContent = role === 'assistant' ? renderMarkdown(content) : escapeHtml(content);

    messageEl.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            ${renderedContent}
        </div>
    `;

    messagesContainer.appendChild(messageEl);
    scrollToBottom();
}

function addTypingIndicator() {
    const el = document.createElement('div');
    el.className = 'message assistant';
    el.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="typing-indicator">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    messagesContainer.appendChild(el);
    scrollToBottom();
    return el;
}

// ── Markdown Rendering (lightweight, same as the Chat page) ──

function renderMarkdown(text) {
    if (!text) return '';

    let html = escapeHtml(text);

    // Code blocks (```...```)
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');

    // Inline code (`...`)
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold (**...**)
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Italic (*...*)
    html = html.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');

    // Unordered lists (- item or * item)
    html = html.replace(/^[\s]*[-*]\s+(.+)$/gm, '<li>$1</li>');
    html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');

    // Ordered lists (1. item)
    html = html.replace(/^[\s]*\d+\.\s+(.+)$/gm, '<li>$1</li>');

    // Headings
    html = html.replace(/^### (.+)$/gm, '<strong>$1</strong>');
    html = html.replace(/^## (.+)$/gm, '<strong>$1</strong>');

    // Line breaks → paragraphs
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');

    // Wrap in paragraph
    html = `<p>${html}</p>`;

    // Clean up empty paragraphs
    html = html.replace(/<p>\s*<\/p>/g, '');

    return html;
}

// ── Utilities ──

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}
