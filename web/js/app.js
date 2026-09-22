/**
 * RAG System — Chat Interface Logic
 * Handles: sending queries, rendering messages, source citations,
 * auto-scroll, Markdown rendering, and system stats.
 */

const API_BASE = '/api';
const messagesContainer = document.getElementById('messages-container');
const queryInput = document.getElementById('query-input');
const sendBtn = document.getElementById('send-btn');
const clearBtn = document.getElementById('clear-chat');
const welcomeMessage = document.getElementById('welcome-message');

// ── Initialize ──

document.addEventListener('DOMContentLoaded', () => {
    loadSystemStats();
    setupInputHandlers();
    setupSidebarToggle();
    queryInput.focus();
});

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
                sendQuery();
            }
        }
    });

    sendBtn.addEventListener('click', () => {
        if (queryInput.value.trim()) {
            sendQuery();
        }
    });

    clearBtn.addEventListener('click', clearChat);
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

// ── Send Query ──

async function sendQuery() {
    const question = queryInput.value.trim();
    if (!question) return;

    // Hide welcome message
    if (welcomeMessage) {
        welcomeMessage.style.display = 'none';
    }

    // Add user message
    addMessage('user', question);

    // Clear input
    queryInput.value = '';
    queryInput.style.height = 'auto';
    sendBtn.disabled = true;

    // Show typing indicator
    const typingEl = addTypingIndicator();

    try {
        const response = await fetch(`${API_BASE}/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question }),
        });

        // Remove typing indicator
        typingEl.remove();

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Server error: ${response.status}`);
        }

        const data = await response.json();

        // Add assistant message with sources
        addMessage('assistant', data.answer, data.sources);

    } catch (error) {
        typingEl.remove();
        addMessage('assistant', `⚠️ Error: ${error.message}. Make sure the server is running and documents are indexed.`);
    }

    queryInput.focus();
}

// ── Ask a suggested question ──

function askQuestion(question) {
    queryInput.value = question;
    sendBtn.disabled = false;
    sendQuery();
}

// ── Message Rendering ──

function addMessage(role, content, sources = []) {
    const messageEl = document.createElement('div');
    messageEl.className = `message ${role}`;

    const avatar = role === 'user' ? '👤' : '🤖';

    let sourcesHtml = '';
    if (sources && sources.length > 0) {
        const chips = sources.map(s =>
            `<span class="source-chip">
                <span class="source-icon">📄</span>
                ${escapeHtml(s.file_name)} (p.${s.page_number})
            </span>`
        ).join('');
        sourcesHtml = `<div class="sources">${chips}</div>`;
    }

    const renderedContent = role === 'assistant' ? renderMarkdown(content) : escapeHtml(content);

    messageEl.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            ${renderedContent}
            ${sourcesHtml}
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

function clearChat() {
    messagesContainer.innerHTML = '';
    if (welcomeMessage) {
        messagesContainer.appendChild(welcomeMessage);
        welcomeMessage.style.display = '';
    }
}

// ── Markdown Rendering (lightweight) ──

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

// ── System Stats ──

async function loadSystemStats() {
    try {
        const response = await fetch(`${API_BASE}/health`);
        if (response.ok) {
            const data = await response.json();
            document.getElementById('stat-chunks').textContent = data.total_chunks;
            document.getElementById('stat-model').textContent = data.gemini_model;
            document.getElementById('stat-embed').textContent = data.embed_model;
        }

        const docsResponse = await fetch(`${API_BASE}/stats`);
        if (docsResponse.ok) {
            const stats = await docsResponse.json();
            document.getElementById('stat-docs').textContent = stats.ingested_files;
        }
    } catch (e) {
        // Stats will show "—" if server is unreachable
        console.warn('Could not load system stats:', e.message);
    }
}
