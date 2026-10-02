document.addEventListener('DOMContentLoaded', () => {
    let appData = null;
    let currentSubmission = null;

    // Elements
    const navLinks = document.querySelectorAll('.nav-links a');
    const queueView = document.getElementById('queue-view');
    const submissionView = document.getElementById('submission-view');
    const queueTitle = document.getElementById('queue-title');
    const tableBody = document.getElementById('queue-table-body');
    const backBtn = document.getElementById('back-btn');

    const popover = document.getElementById('ai-popover');

    // Fetch data
    fetch('/static/tirsweb/data.json')
        .then(res => res.json())
        .then(data => {
            appData = data;
            renderQueue('UNASSIGNED');
        });

    // Navigation
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            navLinks.forEach(l => l.classList.remove('active'));
            e.target.classList.add('active');

            const view = e.target.dataset.view;
            if (view === 'unassigned') {
                queueTitle.textContent = 'Unassigned Queue';
                renderQueue('UNASSIGNED');
            } else {
                queueTitle.textContent = 'Assigned Queue';
                renderQueue('ASSIGNED');
            }
            showView(queueView);
        });
    });

    backBtn.addEventListener('click', () => {
        showView(queueView);
    });

    function showView(viewEl) {
        queueView.classList.add('hidden');
        queueView.classList.remove('active');
        submissionView.classList.add('hidden');
        submissionView.classList.remove('active');

        viewEl.classList.remove('hidden');
        // Force reflow for animation
        void viewEl.offsetWidth;
        viewEl.classList.add('active');
    }

    function renderQueue(status) {
        tableBody.innerHTML = '';
        if (!appData) return;

        const subs = appData.submissions.filter(s => s.status === status);

        subs.forEach(sub => {
            const tr = document.createElement('tr');

            let badgeClass = 'cleared';
            if (sub.clearance_status === 'TA_REVIEW') badgeClass = 'review';
            if (sub.clearance_status === 'CONFLICT') badgeClass = 'conflict';

            // Format a random date for the mockup if not present
            const mockDate = sub.email?.date || "09/22/2026 12:22:29";
            const sender = sub.email?.from || "Velez, Stephanie";
            const subject = sub.email?.subject || "FW: SUBMISSION - " + sub.stitch_worksheet.account_overview.insured_name;

            tr.innerHTML = `
                <td><input type="checkbox"></td>
                <td class="queue-icons">
                    <span class="q-icon" title="Email" onclick="openGlobalPanel('email', '${sub.id}')">📧</span>
                    <span class="q-icon ai-q-icon" title="AI Extracted" onclick="openGlobalPanel('ai', '${sub.id}')">✨</span>
                    <span class="q-icon sum-q-icon" title="1-Page Summary" onclick="openGlobalPanel('summary', '${sub.id}')">📄</span>
                </td>
                <td class="queue-date">${mockDate}</td>
                <td><input type="text" class="queue-input"></td>
                <td><input type="text" class="queue-input"></td>
                <td class="queue-subject">${subject.substring(0, 40)}...</td>
                <td class="queue-sender">${sender}</td>
                <td><button class="btn secondary btn-sm" onclick="openSubmission('${sub.id}')">Review</button></td>
            `;
            tableBody.appendChild(tr);
        });
    }

    // Expose to window for inline onclick
    window.openSubmission = (id) => {
        currentSubmission = appData.submissions.find(s => s.id === id);
        if (!currentSubmission) return;

        document.getElementById('sub-title').textContent = `F-910411443 2026`; // Hardcoded for mockup

        showView(submissionView);

        // Dynamically extract fields from AI
        const formRows = Array.from(document.querySelectorAll('.form-row'));
        const fieldMap = {};

        formRows.forEach(row => {
            const labelEl = row.querySelector('label');
            const inputEl = row.querySelector('.editable-input');

            // Strip any hardcoded badges so they can be replaced by interactive ones
            const existingBadge = row.querySelector('.ai-badge');
            if (existingBadge) existingBadge.remove();

            if (labelEl && inputEl) {
                // Radio buttons are inline-radio so labelEl might not be the actual field name, but let's exclude inline-radio
                if (!row.classList.contains('inline-radio')) {
                    const labelName = labelEl.textContent.replace('*', '').trim();
                    fieldMap[labelName] = inputEl;

                    if (currentSubmission.isSaved && currentSubmission.savedData && currentSubmission.savedData[labelName] !== undefined) {
                        inputEl.value = currentSubmission.savedData[labelName];
                        inputEl.style.color = '';
                    } else {
                        inputEl.value = '✨ Extracting...';
                        inputEl.style.color = '#c084fc';
                    }
                }
            }
        });

        const fieldNames = Object.keys(fieldMap);
        if (fieldNames.length > 0) {
            if (currentSubmission.isSaved) {
                // Restore badges for saved AI extracted data
                for (const key of fieldNames) {
                    if (currentSubmission.provenance && currentSubmission.provenance[key]) {
                        const wrap = fieldMap[key].parentElement;
                        if (!wrap.querySelector('.ai-badge')) {
                            const badge = document.createElement('span');
                            badge.className = 'ai-badge';
                            badge.dataset.key = key;
                            badge.textContent = '✨';
                            badge.addEventListener('mouseenter', showPopover);
                            badge.addEventListener('mouseleave', hidePopover);
                            badge.addEventListener('mousemove', movePopover);
                            wrap.appendChild(badge);
                        }
                    }
                }
            } else {
                const payload = {
                    submission_id: currentSubmission.id,
                    email_body: currentSubmission.email?.body || "No email body",
                    cytora_json: currentSubmission.cytora_entries || {},
                    field_names: fieldNames
                };

                fetch('/api/tirsweb/extract_fields', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                })
                    .then(res => res.json())
                    .then(data => {
                        const extracted = data.extracted_data || {};
                        for (const [key, obj] of Object.entries(extracted)) {
                            if (fieldMap[key]) {
                                const value = typeof obj === 'object' && obj !== null ? obj.value : obj;
                                fieldMap[key].value = value;
                                fieldMap[key].style.color = '';

                                const wrap = fieldMap[key].parentElement;
                                if (!wrap.querySelector('.ai-badge') && value && value !== '-') {
                                    const badge = document.createElement('span');
                                    badge.className = 'ai-badge';
                                    badge.dataset.key = key;

                                    if (!currentSubmission.provenance) currentSubmission.provenance = {};
                                    currentSubmission.provenance[key] = {
                                        action_type: 'EXTRACT',
                                        confidence_score: ((obj.confidence !== undefined ? obj.confidence : 95) / 100),
                                        rationale_short: obj.rationale || 'Dynamically extracted by LLM',
                                        source_name: obj.source || 'LLM Synthesis'
                                    };

                                    badge.textContent = '✨';
                                    badge.addEventListener('mouseenter', showPopover);
                                    badge.addEventListener('mouseleave', hidePopover);
                                    badge.addEventListener('mousemove', movePopover);
                                    wrap.appendChild(badge);
                                }
                            }
                        }
                    })
                    .catch(err => {
                        console.error(err);
                        fieldNames.forEach(key => {
                            if (fieldMap[key] && fieldMap[key].value === '✨ Extracting...') {
                                fieldMap[key].value = '-';
                                fieldMap[key].style.color = '';
                            }
                        });
                    });
            }
        }

        renderWorksheet(currentSubmission);
    };

    function renderWorksheet(sub) {
        // Prevent crashes since we replaced the UI with the mockup
        const accOv = document.getElementById('account-overview');
        if (!accOv) return;

        const dealMet = document.getElementById('deal-metrics');
        const uwEval = document.getElementById('uw-evaluation');

        accOv.innerHTML = ''; dealMet.innerHTML = ''; uwEval.innerHTML = '';

        const renderFields = (target, dataObj) => {
            for (let key in dataObj) {
                if (typeof dataObj[key] === 'object') continue; // Skip nested for simplicity

                const prov = sub.provenance && sub.provenance[key];
                const labelText = key.replace(/_/g, ' ').toUpperCase();

                const div = document.createElement('div');
                div.className = 'field';
                div.innerHTML = `
                    <div class="field-label">
                        ${labelText}
                        ${prov ? `<span class="ai-badge" data-key="${key}">✨</span>` : ''}
                    </div>
                    <div class="field-value">${dataObj[key]}</div>
                `;
                target.appendChild(div);
            }
        };

        if (sub.stitch_worksheet.account_overview) renderFields(accOv, sub.stitch_worksheet.account_overview);
        if (sub.stitch_worksheet.deal_metrics) renderFields(dealMet, sub.stitch_worksheet.deal_metrics);
        if (sub.stitch_worksheet.underwriting_evaluation) renderFields(uwEval, sub.stitch_worksheet.underwriting_evaluation);

        // Bind Popover events
        document.querySelectorAll('.ai-badge').forEach(badge => {
            badge.addEventListener('mouseenter', showPopover);
            badge.addEventListener('mouseleave', hidePopover);
            badge.addEventListener('mousemove', movePopover);
        });
    }

    // Popover Logic
    function showPopover(e) {
        if (!currentSubmission || !currentSubmission.provenance) return;

        const key = e.target.dataset.key;
        const prov = currentSubmission.provenance[key];
        if (!prov) return;

        document.querySelector('.pop-action').textContent = `✨ ${prov.action_type}`;
        document.getElementById('pop-conf-val').textContent = (prov.confidence_score * 100).toFixed(0);
        document.getElementById('pop-reason').textContent = prov.rationale_short;
        document.getElementById('pop-source').textContent = prov.source_name;

        popover.classList.remove('hidden');
        movePopover(e);
    }

    function movePopover(e) {
        // Offset slightly from cursor
        const offset = 15;
        popover.style.left = (e.pageX + offset) + 'px';
        popover.style.top = (e.pageY + offset) + 'px';
    }

    function hidePopover() {
        popover.classList.add('hidden');
    }

    // Side Panels Logic
    const btnEmailPanel = document.getElementById('btn-email-panel');
    const btnAiPanel = document.getElementById('btn-ai-panel');
    const btnSummaryPanel = document.getElementById('btn-summary-panel');
    const sidePanelContainer = document.getElementById('side-panel-container');
    const panelEmail = document.getElementById('panel-email');
    const panelAi = document.getElementById('panel-ai');
    const panelSummary = document.getElementById('panel-summary');
    const closeBtns = document.querySelectorAll('.btn-close-panel');

    function openPanel(panelToShow) {
        sidePanelContainer.classList.remove('hidden');
        panelEmail.classList.add('hidden');
        panelAi.classList.add('hidden');
        panelSummary.classList.add('hidden');
        panelToShow.classList.remove('hidden');
    }

    function closePanel() {
        sidePanelContainer.classList.add('hidden');
    }

    // Expose for queue icons
    window.openGlobalPanel = (type, id) => {
        if (id) {
            currentSubmission = appData.submissions.find(s => s.id === id);
            if (currentSubmission) {

                // 1. Update Email Panel
                const subjectEl = document.querySelector('.email-subject-line');
                if (subjectEl) subjectEl.textContent = currentSubmission.email?.subject || '';

                const fromEl = document.querySelector('.email-from');
                if (fromEl) {
                    fromEl.textContent = currentSubmission.email?.from || '';
                    fromEl.style.color = '#000';
                }

                const dateEl = document.querySelector('.email-date');
                if (dateEl) dateEl.textContent = currentSubmission.email?.date || '';

                const toEl = document.querySelector('.email-to');
                if (toEl) {
                    toEl.textContent = currentSubmission.email?.to || '';
                    toEl.style.color = '#000';
                }

                const ccEl = document.querySelector('.email-cc');
                if (ccEl) {
                    ccEl.textContent = currentSubmission.email?.cc || '';
                    ccEl.style.color = '#000';
                }

                const attEl = document.querySelector('.att-name');
                if (attEl) {
                    // Extracting the first file name if there is an attachment, otherwise hide it or show a dummy
                    const filename = currentSubmission.email?.filename || '';
                    if (filename) {
                        attEl.textContent = filename;
                    }
                }

                const emailContent = document.querySelector('.light-email-view .email-content');
                if (emailContent && currentSubmission.email?.body) {
                    // Inject HTML directly to support formatting, tables, signature images from the .eml
                    emailContent.innerHTML = currentSubmission.email.body;
                }

                // 2. Update AI Preview Table
                const aiTbody = document.querySelector('#panel-ai .ai-diff-table tbody');
                if (aiTbody && currentSubmission.cytora_entries) {
                    aiTbody.innerHTML = '';
                    currentSubmission.cytora_entries.forEach(entry => {
                        const tr = document.createElement('tr');
                        // Some basic mock mapping for confidence/change
                        const conf = entry.ConfidenceIndex || "100";
                        const confClass = conf > 90 ? "high" : "review";

                        tr.innerHTML = `
                            <td>${entry.FieldName || 'N/A'}</td>
                            <td><span class="conf-badge ${confClass}">${conf}</span></td>
                            <td>${entry.ExtractedValue || ''}</td>
                            <td>${entry.InternalCode || entry.ExtractedValue || ''}</td>
                            <td><input type="checkbox" ${entry.TAChange ? 'checked' : ''}></td>
                        `;
                        aiTbody.appendChild(tr);
                    });
                }

                // 3. Update 1-Page Summary
                const summaryBody = document.querySelector('#panel-summary .summary-card');
                if (summaryBody && type === 'summary') {
                    
                    const fetchSummary = (force = false) => {
                        summaryBody.innerHTML = '<div style="padding: 2rem; text-align: center; color: var(--text-secondary);">✨ ' + (force ? 'Re-generating' : 'Fetching') + ' AI summary...</div>';

                        const payload = {
                            submission_id: currentSubmission.id,
                            email_body: currentSubmission.email?.body || "No email body provided.",
                            cytora_json: currentSubmission.cytora_entries || {},
                            force_regenerate: force
                        };

                        fetch('/api/tirsweb/summarize', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(payload)
                        })
                            .then(res => res.json())
                            .then(data => {
                                if (data.summary_html) {
                                    summaryBody.innerHTML = `
                                        ${data.summary_html}
                                        <div style="margin-top: 2rem; display: flex; gap: 1rem;">
                                            <button class="btn primary btn-sm">Generate Final Document</button>
                                            <button class="btn secondary btn-sm" id="btn-regen-summary">Regenerate Summary</button>
                                        </div>
                                    `;
                                    
                                    const regenBtn = summaryBody.querySelector('#btn-regen-summary');
                                    if (regenBtn) {
                                        regenBtn.addEventListener('click', () => fetchSummary(true));
                                    }
                                } else {
                                    summaryBody.innerHTML = '<div style="color: red; padding: 1rem;">Failed to generate summary.</div><button class="btn secondary btn-sm" id="btn-regen-summary">Retry</button>';
                                    summaryBody.querySelector('#btn-regen-summary')?.addEventListener('click', () => fetchSummary(true));
                                }
                            })
                            .catch(err => {
                                console.error('Summary generation error:', err);
                                summaryBody.innerHTML = '<div style="color: red; padding: 1rem;">An error occurred while generating the summary.</div><button class="btn secondary btn-sm" id="btn-regen-summary">Retry</button>';
                                summaryBody.querySelector('#btn-regen-summary')?.addEventListener('click', () => fetchSummary(true));
                            });
                    };
                    
                    fetchSummary(false);
                }
            }
        }

        if (type === 'email') openPanel(panelEmail);
        if (type === 'ai') openPanel(panelAi);
        if (type === 'summary') openPanel(panelSummary);
    };

    if (btnEmailPanel) {
        btnEmailPanel.addEventListener('click', () => {
            if (currentSubmission) {
                window.openGlobalPanel('email', currentSubmission.id);
            } else {
                openPanel(panelEmail);
            }
        });
    }

    if (btnAiPanel) {
        btnAiPanel.addEventListener('click', () => {
            if (currentSubmission) {
                window.openGlobalPanel('ai', currentSubmission.id);
            } else {
                openPanel(panelAi);
            }
        });
    }

    if (btnSummaryPanel) {
        btnSummaryPanel.addEventListener('click', () => {
            if (currentSubmission) {
                window.openGlobalPanel('summary', currentSubmission.id);
            } else {
                openPanel(panelSummary);
            }
        });
    }

    closeBtns.forEach(btn => {
        btn.addEventListener('click', closePanel);
    });

    // Tab Logic
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            tabBtns.forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');
        });
    });

    // Make fields editable dynamically
    document.querySelectorAll('.input-wrap').forEach(wrap => {
        const textNodes = Array.from(wrap.childNodes).filter(n => n.nodeType === Node.TEXT_NODE);
        if (textNodes.length > 0) {
            const mainTextNode = textNodes[0];
            const text = mainTextNode.nodeValue.trim();
            if (text !== '') {
                const input = document.createElement('input');
                input.type = 'text';
                input.className = 'editable-input';
                input.value = text === '-' ? '' : text;
                wrap.replaceChild(input, mainTextNode);
            }
        } else if (wrap.children.length === 0) {
            const input = document.createElement('input');
            input.type = 'text';
            input.className = 'editable-input';
            wrap.appendChild(input);
        }
    });

    // Wire up buttons
    document.getElementById('btn-save')?.addEventListener('click', () => {
        if (currentSubmission) {
            currentSubmission.savedData = {};
            const formRows = Array.from(document.querySelectorAll('.form-row'));
            formRows.forEach(row => {
                const labelEl = row.querySelector('label');
                const inputEl = row.querySelector('.editable-input');
                if (labelEl && inputEl && !row.classList.contains('inline-radio')) {
                    const labelName = labelEl.textContent.replace('*', '').trim();
                    currentSubmission.savedData[labelName] = inputEl.value;
                }
            });
            currentSubmission.isSaved = true;
        }

        const btn = document.getElementById('btn-save');
        const origText = btn.textContent;
        btn.textContent = 'Saved!';
        setTimeout(() => btn.textContent = origText, 2000);
    });

    document.getElementById('btn-activities')?.addEventListener('click', () => {
        alert('Activities panel functionality is working as expected.');
    });

    document.getElementById('btn-actions')?.addEventListener('click', () => {
        alert('Actions menu functionality is working as expected.');
    });

    document.getElementById('btn-auto-quote')?.addEventListener('click', () => {
        const btn = document.getElementById('btn-auto-quote');
        btn.innerHTML = '✨ Processing...';
        setTimeout(() => {
            btn.innerHTML = '✨ Quote Bound!';
            btn.style.background = 'var(--success)';
            btn.style.borderColor = 'var(--success)';
        }, 1500);
    });

    // Chatbot Logic
    const chatbotToggleBtn = document.getElementById('chatbot-toggle-btn');
    const chatbotPanel = document.getElementById('chatbot-panel');
    const closeChatbotBtn = document.getElementById('close-chatbot-btn');
    const chatbotInput = document.getElementById('chatbot-input');
    const chatbotSendBtn = document.getElementById('chatbot-send-btn');
    const chatbotMessages = document.getElementById('chatbot-messages');

    if (chatbotToggleBtn) {
        chatbotToggleBtn.addEventListener('click', () => {
            chatbotPanel.classList.remove('hidden');
        });
    }

    if (closeChatbotBtn) {
        closeChatbotBtn.addEventListener('click', () => {
            chatbotPanel.classList.add('hidden');
        });
    }

    function handleSendChatMessage(inputEl, messagesEl) {
        if (!inputEl || !messagesEl) return;
        const text = inputEl.value.trim();
        if (!text) return;

        const appendMsg = (txt, sender) => {
            const msgDiv = document.createElement('div');
            msgDiv.className = `chat-msg ${sender}-msg`;
            msgDiv.innerHTML = `<p>${txt}</p>`;
            messagesEl.appendChild(msgDiv);
            messagesEl.scrollTop = messagesEl.scrollHeight;
        };

        appendMsg(text, 'user');
        inputEl.value = '';

        // Generate context from current submission
        let contextStr = "No active submission context.";
        if (currentSubmission) {
            contextStr = `Submission ID: ${currentSubmission.id}
Status: ${currentSubmission.status || 'Unknown'}
Clearance Status: ${currentSubmission.clearance_status || 'Unknown'}
Email Subject: ${currentSubmission.email?.subject || 'None'}
Email From: ${currentSubmission.email?.from || 'None'}
Email Body: ${currentSubmission.email?.body || 'None'}
Stitch Worksheet Data: ${JSON.stringify(currentSubmission.stitch_worksheet || {})}
Cytora Extracted Data: ${JSON.stringify(currentSubmission.cytora_entries || {})}`;
        }

        const payload = {
            message: text,
            submission_context: contextStr
        };

        // Show typing indicator
        const typingId = 'typing-' + Date.now() + Math.floor(Math.random()*1000);
        const typingDiv = document.createElement('div');
        typingDiv.className = 'chat-msg ai-msg';
        typingDiv.id = typingId;
        typingDiv.innerHTML = `<p>...</p>`;
        messagesEl.appendChild(typingDiv);
        messagesEl.scrollTop = messagesEl.scrollHeight;

        fetch('/api/tirsweb/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
            document.getElementById(typingId)?.remove();
            appendMsg(data.reply, 'ai');
        })
        .catch(err => {
            console.error(err);
            document.getElementById(typingId)?.remove();
            appendMsg('Failed to connect to TA Assistant.', 'ai');
        });
    }

    if (chatbotSendBtn) {
        chatbotSendBtn.addEventListener('click', () => handleSendChatMessage(chatbotInput, chatbotMessages));
    }

    if (chatbotInput) {
        chatbotInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                handleSendChatMessage(chatbotInput, chatbotMessages);
            }
        });
    }

    // Inline Summary Chatbot Logic
    const summaryChatInput = document.getElementById('summary-chat-input');
    const summaryChatSendBtn = document.getElementById('summary-chat-send-btn');
    const summaryChatMessages = document.getElementById('summary-chat-messages');

    if (summaryChatSendBtn) {
        summaryChatSendBtn.addEventListener('click', () => handleSendChatMessage(summaryChatInput, summaryChatMessages));
    }

    if (summaryChatInput) {
        summaryChatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                handleSendChatMessage(summaryChatInput, summaryChatMessages);
            }
        });
    }

});
