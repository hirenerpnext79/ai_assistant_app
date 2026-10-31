// ai_assistant.js
frappe.provide("hns_ai_assistant_app");

const CHATBOT_LABEL = "Ask Akansha";

hns_ai_assistant_app.Assistant = {
    init: function () {
        frappe.call({
            method: "frappe.client.get",
            args: { doctype: "Hns AI Assistant App Setting", name: "Hns AI Assistant App Setting" },
            callback: (r) => {
                const settings = r.message || {};
                this.chatbot_icon = settings.chatbot_icon || "/assets/hns_ai_assistant_app/images/akansha_icon.webp";
                this.enable_erpnext_context = settings.enable_erpnext_context === undefined ? 1 : settings.enable_erpnext_context;
                this.full_width = settings.full_width === 1;
                this.load_allowed_providers();
            }
        });
    },

    load_allowed_providers: function () {
        frappe.call({
            method: "hns_ai_assistant_app.api.ai_handler.get_allowed_providers",
            callback: (r) => {
                this.allowed_providers = r.message || [];
                this.selected_provider = null;

                const default_provider = this.allowed_providers.find(p => p.is_default);
                if (default_provider) {
                    this.selected_provider = default_provider.name;
                } else if (this.allowed_providers.length > 0) {
                    this.selected_provider = this.allowed_providers[0].name;
                }

                this.setup_ui();
                this.bind_events();
                
                if (this.allowed_providers.length === 0) {
                    this.input.disabled = true;
                    this.input.placeholder = "Chat disabled (No Provider)";
                    const send_btn = document.getElementById("ask-akansha-send");
                    if (send_btn) send_btn.disabled = true;
                    document.querySelector('.aak-input-wrapper').style.display = 'none';
                    this.messages.innerHTML = `<div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; text-align:center; padding: 20px; color: #ef4444;">
                            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom:10px;"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                            <h3 style="margin-bottom:5px; font-weight:600;">Access Denied</h3>
                            <p style="font-size:13.5px;">At least one provider needs to be active on chat.</p>
                        </div>`;
                }
            }
        });
    },

    get_quick_questions_erp: function() {
        return [
            "What Payment Entries are pending collection today?",
            "List all overdue Sales Invoices.",
            "What is the total outstanding amount for all Customers?",
            "Show me a summary of today's Sales Orders and Sales Invoices.",
            "List all Purchase Orders and Purchase Receipts made today.",
            "Which Employees have an absent Attendance record today?",
            "Which Employees are missing an Employee Checkin today?",
            "Which Sales Orders are waiting for a Delivery Note?",
            "Which Purchase Orders are waiting for a Purchase Receipt?",
            "Which Items are running low in stock based on Bin actual qty?"
        ];
    },

    get_quick_questions_general: function() {
        return [
            "How do I create a new Sales Invoice in ERPNext?",
            "What is the process for bank reconciliation in ERPNext?",
            "How do I manage user permissions in ERPNext?",
            "Explain the manufacturing routing process in ERPNext.",
            "How do I create a custom Doctype in ERPNext?",
            "What is the best way to handle inventory valuation in ERPNext?",
            "How do I set up a recurring Journal Entry in ERPNext?",
            "Explain how Pricing Rules work in ERPNext.",
            "How can I customize a Print Format in ERPNext?",
            "Difference between Sales Order & Delivery Note in ERPNext?"
        ];
    },

    setup_ui: function () {
        // Floating button
        const btn = document.createElement("button");
        btn.id = "ask-akansha-btn";
        btn.innerHTML = `<img src="${this.chatbot_icon}" alt="${CHATBOT_LABEL}">`;
        btn.title = CHATBOT_LABEL;
        document.body.appendChild(btn);

        // Provider options
        const provider_options = (this.allowed_providers || []).map(p => {
            const sel = p.name === this.selected_provider ? "selected" : "";
            return `<div class="aak-select-option ${sel}" data-value="${p.name}">${p.provider_name}</div>`;
        }).join("");

        const selected_p = (this.allowed_providers || []).find(p => p.name === this.selected_provider) || {provider_name: "Select Provider"};
        
        const provider_html = `
            <div class="aak-custom-select" id="ask-akansha-custom-select">
                <div class="aak-select-trigger" id="ask-akansha-select-trigger">
                    <span id="ask-akansha-selected-text" style="display: inline-block; max-width: 140px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; vertical-align: middle;">${selected_p.provider_name}</span>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#6b7280" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
                </div>
                <div class="aak-select-options" id="ask-akansha-select-options">
                    ${provider_options}
                </div>
            </div>
        `;

        const context_checked = this.enable_erpnext_context ? "checked" : "";
        const fw_checked = this.full_width ? "checked" : "";

        this.quick_questions_erp = this.get_quick_questions_erp();
        this.quick_questions_general = this.get_quick_questions_general();
        
        this.qq_html_erp = this.quick_questions_erp.map(q => `<div class="aak-select-option aak-qq-option" style="white-space: normal; line-height: 1.4; border-bottom: 1px solid #f3f4f6;">${q}</div>`).join("");
        this.qq_html_general = this.quick_questions_general.map(q => `<div class="aak-select-option aak-qq-option" style="white-space: normal; line-height: 1.4; border-bottom: 1px solid #f3f4f6;">${q}</div>`).join("");
        
        const panel = document.createElement("div");
        panel.id = "ask-akansha-panel";
        if (this.full_width) panel.classList.add("full-width");

        panel.innerHTML = `
            <div class="aak-header">
                <div class="aak-header-left">
                    <div class="aak-avatar">
                        <img src="${this.chatbot_icon}" alt="${CHATBOT_LABEL}">
                        <span class="aak-status-dot"></span>
                    </div>
                    <div class="aak-header-info">
                        <span class="aak-header-name">${CHATBOT_LABEL}</span>
                        <span class="aak-header-sub">AI Assistant &bull; Online</span>
                    </div>
                </div>
                <div class="aak-header-actions">
                    <button class="aak-icon-btn ${this.full_width ? 'active' : ''}" id="ask-akansha-fullwidth-btn" title="Toggle Full Width">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="15 3 21 3 21 9"></polyline>
                            <polyline points="9 21 3 21 3 15"></polyline>
                            <line x1="21" y1="3" x2="14" y2="10"></line>
                            <line x1="3" y1="21" x2="10" y2="14"></line>
                        </svg>
                    </button>
                    <button class="aak-icon-btn" id="ask-akansha-close" title="Close">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                    </button>
                </div>
            </div>

            <div id="ask-akansha-messages"></div>

            <div class="aak-input-wrapper">
                
                <div class="aak-input-row">
                    <input type="text" id="ask-akansha-input" placeholder="Ask me anything..." autocomplete="off">
                    <button id="ask-akansha-send" class="aak-send-btn">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <line x1="22" y1="2" x2="11" y2="13"></line>
                            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                        </svg>
                    </button>
                </div>
                <div class="aak-footer" style="position: relative;">
                    <div class="aak-footer-left">
                        ${this.allowed_providers && this.allowed_providers.length > 0 ? `
                        <div class="aak-control-chip">
                            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/></svg>
                            ${provider_html}
                        </div>
                        ` : ""}
                        
                        <div class="aak-custom-select" id="ask-akansha-settings-select" style="position: static;">
                            <button class="aak-icon-btn" id="ask-akansha-settings-trigger" title="Settings" style="width: 32px; height: 32px; border: none; background: transparent;">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6b7280" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <circle cx="12" cy="12" r="3"></circle>
                                    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                                </svg>
                            </button>
                            <div class="aak-select-options" id="ask-akansha-settings-options" style="left: 12px; bottom: calc(100% + 12px); width: calc(100% - 24px); min-width: unset; padding: 0; cursor: default; transform-origin: bottom left; box-sizing: border-box; border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,0.12);">
                                
                                <div style="padding: 12px 16px; border-bottom: 1px solid #f3f4f6; display: flex; align-items: center; justify-content: space-between; cursor: default;">
                                    <span style="font-size: 13px; font-weight: 500; color: #374151;">ERP Context</span>
                                    <label class="aak-toggle-label" title="Enable ERPNext Context" style="margin: 0; cursor: pointer;">
                                        <input type="checkbox" id="ask-akansha-enable-context" ${context_checked} class="aak-toggle-input">
                                        <span class="aak-toggle-track"></span>
                                    </label>
                                </div>

                                <div id="ask-akansha-qq-container" style="display: block;">
                                    <div style="padding: 12px 16px 8px; cursor: default;">
                                        <span id="ask-akansha-qq-title" style="font-size: 11px; font-weight: 700; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.5px;">${this.enable_erpnext_context ? 'ERPNext Questions' : 'General Questions'}</span>
                                    </div>
                                    <div class="aak-options-list" id="ask-akansha-qq-list" style="max-height: 220px;">
                                        ${this.enable_erpnext_context ? this.qq_html_erp : this.qq_html_general}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(panel);

        this.panel = document.getElementById("ask-akansha-panel");
        this.input = document.getElementById("ask-akansha-input");
        this.messages = document.getElementById("ask-akansha-messages");

        this.load_chat_history();
    },

    load_chat_history: function () {
        if (this.allowed_providers && this.allowed_providers.length === 0) return;
        frappe.call({
            method: "hns_ai_assistant_app.api.ai_handler.get_chat_history",
            callback: (r) => {
                if (r.message && r.message.length > 0) {
                    r.message.forEach(log => {
                        if (log.user_query) this.add_message_to_dom(log.user_query, "user", log.creation);
                        if (log.ai_response) this.add_message_to_dom(log.ai_response, "akansha", log.creation);
                    });

                } else if (!this.allowed_providers || this.allowed_providers.length > 0) {
                    this.add_message_to_dom("Hello! 👋 How can I help you today?", "akansha");
                }
                
                if (this.allowed_providers && this.allowed_providers.length === 0) {
                    this.add_message_to_dom("At least one provider is needed for this chat to work. Please check permissions.", "akansha");
                }
            }
        });
    },

    bind_events: function () {
        document.getElementById("ask-akansha-btn").addEventListener("click", () => this.toggle_panel());
        document.getElementById("ask-akansha-close").addEventListener("click", () => this.close_panel());
        document.getElementById("ask-akansha-send").addEventListener("click", () => this.send_message());

        this.input.addEventListener("keypress", (e) => {
            if (e.key === "Enter") this.send_message();
        });

        const fw_btn = document.getElementById("ask-akansha-fullwidth-btn");
        if (fw_btn) {
            fw_btn.addEventListener("click", () => this.toggle_full_width());
        }



        const custom_select = document.getElementById("ask-akansha-custom-select");
        if (custom_select) {
            const trigger = document.getElementById("ask-akansha-select-trigger");
            const options_container = document.getElementById("ask-akansha-select-options");
            const selected_text = document.getElementById("ask-akansha-selected-text");
            
            trigger.addEventListener("click", (e) => {
                e.stopPropagation();
                custom_select.classList.toggle("open");
                const s_select = document.getElementById("ask-akansha-settings-select");
                if (s_select) s_select.classList.remove("open");
            });

            document.addEventListener("click", () => {
                custom_select.classList.remove("open");
            });

            options_container.querySelectorAll(".aak-select-option").forEach(opt => {
                opt.addEventListener("click", (e) => {
                    this.selected_provider = e.target.closest(".aak-select-option").getAttribute("data-value");
                    let text = e.target.closest(".aak-select-option").textContent.trim();
                    selected_text.textContent = text;
                    options_container.querySelectorAll(".aak-select-option").forEach(o => {
                        o.classList.remove("selected");
                    });
                    e.target.closest(".aak-select-option").classList.add("selected");
                });
            });
        }
        const s_select = document.getElementById("ask-akansha-settings-select");
        if (s_select) {
            const trigger = document.getElementById("ask-akansha-settings-trigger");
            trigger.addEventListener("click", (e) => {
                e.stopPropagation();
                s_select.classList.toggle("open");
                const p_select = document.getElementById("ask-akansha-custom-select");
                if (p_select) p_select.classList.remove("open");
            });

            // Prevent closing when clicking inside settings area (except questions)
            s_select.querySelector('.aak-select-options').addEventListener("click", (e) => {
                if (!e.target.closest('.aak-qq-option')) {
                    e.stopPropagation();
                }
            });

            const ctx_toggle = document.getElementById("ask-akansha-enable-context");
            if (ctx_toggle) {
                ctx_toggle.addEventListener("change", (e) => {
                    const qq_list = document.getElementById("ask-akansha-qq-list");
                    const qq_title = document.getElementById("ask-akansha-qq-title");
                    if (qq_list && qq_title) {
                        qq_title.textContent = e.target.checked ? 'ERPNext Questions' : 'General Questions';
                        qq_list.innerHTML = e.target.checked ? this.qq_html_erp : this.qq_html_general;
                        
                        // Re-bind click events for newly inserted options
                        document.querySelectorAll(".aak-qq-option").forEach(qq => {
                            qq.addEventListener("click", (ev) => {
                                this.input.value = ev.target.textContent.trim();
                                this.send_message();
                                s_select.classList.remove("open");
                            });
                        });
                    }
                });
            }

            document.querySelectorAll(".aak-qq-option").forEach(qq => {
                qq.addEventListener("click", (e) => {
                    this.input.value = e.target.textContent.trim();
                    this.send_message();
                    s_select.classList.remove("open");
                });
            });
            
            document.addEventListener("click", (e) => {
                if (!s_select.contains(e.target)) s_select.classList.remove("open");
            });
        }
    },

    toggle_full_width: function (force) {
        const is_fw = force !== undefined ? force : !this.panel.classList.contains("full-width");
        this.panel.classList.toggle("full-width", is_fw);

        const fw_btn = document.getElementById("ask-akansha-fullwidth-btn");
        if (fw_btn) fw_btn.classList.toggle("active", is_fw);

        this.full_width = is_fw;
        this.messages.scrollTop = this.messages.scrollHeight;
    },

    toggle_panel: function () {
        this.panel.classList.toggle("active");
        if (this.panel.classList.contains("active")) {
            this.input.focus();
            this.messages.scrollTop = this.messages.scrollHeight;
        }
    },

    close_panel: function () {
        this.panel.classList.remove("active");
    },

    open_panel: function () {
        if (!this.panel) return;
        if (!this.panel.classList.contains("active")) {
            this.toggle_panel();
        }
    },

    set_provider: function (provider_id) {
        if (!provider_id) return;
        this.selected_provider = provider_id;
        const options_container = document.getElementById("ask-akansha-select-options");
        const selected_text = document.getElementById("ask-akansha-selected-text");
        if (options_container && selected_text) {
            options_container.querySelectorAll(".aak-select-option").forEach(o => {
                if (o.getAttribute("data-value") === provider_id) {
                    o.classList.add("selected");
                    selected_text.textContent = o.textContent.trim();
                } else {
                    o.classList.remove("selected");
                }
            });
        }
    },

    ask_prompt: function (prompt_text, provider_override) {
        if (!prompt_text) return;
        this.open_panel();

        if (provider_override) {
            this.set_provider(provider_override);
        } else if (this.allowed_providers && this.allowed_providers.length > 0) {
            const gemini = this.allowed_providers.find(p =>
                (p.provider_name || p.name || "").toLowerCase().includes("gemini")
            );
            if (gemini) {
                this.set_provider(gemini.name);
            }
        }

        setTimeout(() => {
            this.send_message(prompt_text);
        }, 150);
    },

    set_processing: function (processing) {
        this.is_processing = processing;
        this.input.disabled = processing;
        const send_btn = document.getElementById("ask-akansha-send");
        if (send_btn) send_btn.disabled = processing;
        this.panel.classList.toggle("aak-processing", processing);

        const custom_select = document.getElementById("ask-akansha-custom-select");
        if (custom_select) custom_select.classList.toggle("disabled", processing);
        const ctx_check = document.getElementById("ask-akansha-enable-context");
        if (ctx_check) ctx_check.disabled = processing;

        const fw_btn = document.getElementById("ask-akansha-fullwidth-btn");
        if (fw_btn) fw_btn.disabled = processing;
        document.querySelectorAll(".aak-quick-question").forEach(qq => qq.style.pointerEvents = processing ? "none" : "auto");
    },

    show_thinking: function () {
        const thinking = document.createElement("div");
        thinking.id = "aak-thinking-bubble";
        thinking.className = "chat-message akansha aak-thinking";
        thinking.innerHTML = `
            <div class="aak-dots">
                <span></span><span></span><span></span>
            </div>
            <span class="aak-thinking-text">Thinking…</span>
        `;
        this.messages.appendChild(thinking);
        this.messages.scrollTop = this.messages.scrollHeight;
    },

    hide_thinking: function () {
        const el = document.getElementById("aak-thinking-bubble");
        if (el) el.remove();
    },

    send_message: function (custom_text) {
        if (this.is_processing) return;

        const text = (custom_text !== undefined ? custom_text : (this.input ? this.input.value : "")).trim();
        if (!text) return;

        this.add_message_to_dom(text, "user");
        if (this.input) this.input.value = "";
        const qq_wrap = document.getElementById("aak-quick-questions-wrapper");
        if (qq_wrap) qq_wrap.style.display = "none";

        this.set_processing(true);
        this.show_thinking();

        const enable_context_checkbox = document.getElementById("ask-akansha-enable-context");
        const enable_context = enable_context_checkbox
            ? enable_context_checkbox.checked
            : (this.enable_erpnext_context ? true : false);

        frappe.call({
            method: "hns_ai_assistant_app.api.ai_handler.ask_akansha",
            args: {
                message: text,
                provider_name: this.selected_provider || null,
                enable_context: enable_context ? 1 : 0,
                context: { route: frappe.get_route ? frappe.get_route() : null }
            },
            callback: (r) => {
                this.hide_thinking();
                if (r.message) {
                    this.add_message_to_dom(r.message, "akansha");
                }
            },
            always: () => {
                this.hide_thinking();
                this.set_processing(false);
                this.input.focus();
            }
        });
    },

    format_markdown_tables: function (text) {
        if (!text || text.indexOf("|") === -1) return text;

        let normalized = text.replace(/\|\|\s*\|/g, "|\n|");
        normalized = normalized.replace(/\|\|\s*([^\s|])/g, "|\n|$1");

        const table_regex = /((?:\|[^\n\r]+\|\r?\n?)+)/g;
        return normalized.replace(table_regex, function (match) {
            const lines = match.split(/\r?\n/).map(l => l.trim()).filter(l => l.startsWith("|") && l.endsWith("|"));
            if (lines.length < 2) return match;
            const is_sep = /^\|[\s\-:|]+\|$/.test(lines[1]);
            if (!is_sep) return match;

            const parse_cells = (row) => row.slice(1, -1).split("|").map(c => c.trim());
            const headers = parse_cells(lines[0]);
            const header_html = headers.map(h => `<th style="padding: 9px 14px; font-weight: 600; font-size: 11.5px; color: #475569; text-transform: uppercase; letter-spacing: 0.4px; border-bottom: 2px solid #cbd5e1; background: #f8fafc; white-space: nowrap !important; word-break: normal !important; position: sticky; top: 0;">${h}</th>`).join("");

            const rows_html = [];
            for (let i = 2; i < lines.length; i++) {
                const cells = parse_cells(lines[i]);
                if (cells.length === 0 || (cells.length === 1 && cells[0] === "")) continue;
                const row_cells = cells.map(c => `<td style="padding: 9px 14px; color: #1e293b; border-bottom: 1px solid #f1f5f9; white-space: nowrap !important; word-break: normal !important;">${c}</td>`).join("");
                rows_html.push(`<tr>${row_cells}</tr>`);
            }

            return `\n<div class="aak-table-container" style="margin: 8px 0; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); overflow: hidden; width: 100%; max-width: 100%; min-width: 0;"><div class="aak-table-scroll" style="width: 100%; max-width: 100%; overflow-x: auto; overflow-y: hidden; -webkit-overflow-scrolling: touch; display: block;"><table class="aak-data-table" style="width: max-content; min-width: 100%; border-collapse: collapse; font-size: 12px; line-height: 1.5; text-align: left; table-layout: auto; margin: 0;"><thead><tr>${header_html}</tr></thead><tbody>${rows_html.join("")}</tbody></table></div></div>\n`;
        });
    },

    render_markdown: function (text) {
        if (!text) return "";

        if (typeof showdown !== "undefined") {
            try {
                showdown.setOption("tables", true);
                showdown.setOption("simpleLineBreaks", true);
            } catch (e) {}
        }

        let processed = this.format_markdown_tables(text);
        let html = typeof frappe.markdown !== "undefined" ? frappe.markdown(processed) : processed;

        const temp = document.createElement("div");
        temp.innerHTML = html;
        const tables = temp.querySelectorAll("table");
        tables.forEach((table) => {
            if (!table.parentElement || !table.parentElement.classList.contains("aak-table-scroll")) {
                const container = document.createElement("div");
                container.className = "aak-table-container";
                container.style.cssText = "margin: 8px 0; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); overflow: hidden; width: 100%; max-width: 100%; min-width: 0;";
                const wrapper = document.createElement("div");
                wrapper.className = "aak-table-scroll";
                wrapper.style.cssText = "width: 100%; max-width: 100%; overflow-x: auto; overflow-y: hidden; -webkit-overflow-scrolling: touch; display: block;";
                table.classList.add("aak-data-table");
                table.style.cssText = "width: max-content; min-width: 100%; border-collapse: collapse; font-size: 12px; line-height: 1.5; text-align: left; table-layout: auto; margin: 0;";
                table.querySelectorAll("th").forEach(th => {
                    th.style.cssText = "padding: 9px 14px; font-weight: 600; font-size: 11.5px; color: #475569; text-transform: uppercase; letter-spacing: 0.4px; border-bottom: 2px solid #cbd5e1; background: #f8fafc; white-space: nowrap !important; word-break: normal !important; position: sticky; top: 0;";
                });
                table.querySelectorAll("td").forEach(td => {
                    td.style.cssText = "padding: 9px 14px; color: #1e293b; border-bottom: 1px solid #f1f5f9; white-space: nowrap !important; word-break: normal !important;";
                });
                table.parentNode.insertBefore(container, table);
                container.appendChild(wrapper);
                wrapper.appendChild(table);
            }
        });

        const ol_list = temp.querySelectorAll("ol");
        if (ol_list.length > 1) {
            let running_index = 0;
            ol_list.forEach((ol, idx) => {
                if (idx === 0) {
                    running_index = ol.querySelectorAll(":scope > li").length;
                } else {
                    let prev = ol.previousElementSibling;
                    if (prev && (prev.tagName === "UL" || prev.tagName === "OL" || prev.tagName === "P" || prev.tagName === "DIV")) {
                        ol.setAttribute("start", running_index + 1);
                        running_index += ol.querySelectorAll(":scope > li").length;
                    } else {
                        running_index = ol.querySelectorAll(":scope > li").length;
                    }
                }
            });
        }

        return temp.innerHTML;
    },

    add_message_to_dom: function (text, sender, creation = null) {
        if (!text) return;

        const now = creation ? new Date(creation) : new Date();
        const date_key = now.toLocaleDateString();

        if (this.last_msg_date !== date_key) {
            const formatted_date = now.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
            const date_html = `<div style="text-align: center; margin: -10px 0 4px;"><span style="display: inline-block; background-color: #f3f4f6; color: #4b5563; font-size: 10px; font-weight: 600; padding: 3px 10px; border-radius: 12px; letter-spacing: 0.2px;">${formatted_date}</span></div>`;
            this.messages.insertAdjacentHTML('beforeend', date_html);
            this.last_msg_date = date_key;
        }

        const wrapper = document.createElement("div");
        wrapper.className = `aak-msg-row aak-msg-${sender}`;

        const bubble = document.createElement("div");
        bubble.className = `chat-message ${sender}`;

        const content_div = document.createElement("div");
        content_div.className = "msg-content";
        if (sender === "akansha") {
            content_div.innerHTML = this.render_markdown(text);
            if (content_div.querySelector(".aak-table-container, .aak-table-scroll, table")) {
                bubble.classList.add("has-table");
                wrapper.classList.add("has-table");
            }
        } else {
            content_div.textContent = text;
        }
        bubble.appendChild(content_div);

        const time_div = document.createElement("div");
        time_div.className = "aak-msg-time";
        time_div.textContent = now.toLocaleTimeString([], { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
        bubble.appendChild(time_div);
        
        wrapper.appendChild(bubble);

        this.messages.appendChild(wrapper);
        this.messages.scrollTop = this.messages.scrollHeight;
    }
};

hns_ai_assistant_app.ReportPrompt = {
    prompt_cache: {},

    init: function () {
        this.setup_query_report_interceptor();
        this.bind_route_events();
    },

    setup_query_report_interceptor: function () {
        const me = this;
        if (frappe.views && frappe.views.QueryReport) {
            me.patch_query_report(frappe.views.QueryReport);
        }

        if (frappe.views) {
            let _qr = frappe.views.QueryReport;
            try {
                Object.defineProperty(frappe.views, "QueryReport", {
                    configurable: true,
                    enumerable: true,
                    get: function () {
                        return _qr;
                    },
                    set: function (val) {
                        _qr = val;
                        me.patch_query_report(val);
                    }
                });
            } catch (e) {
                // Ignore if property is non-configurable
            }
        }
    },

    patch_query_report: function (QueryReportClass) {
        if (!QueryReportClass || QueryReportClass._hns_report_prompt_patched) return;
        QueryReportClass._hns_report_prompt_patched = true;

        const original_load_report = QueryReportClass.prototype.load_report;
        const me = this;

        QueryReportClass.prototype.load_report = function (route_options) {
            const res = original_load_report.apply(this, arguments);
            const report_inst = this;
            if (res && res.then) {
                res.then(() => {
                    setTimeout(() => me.attach_button(report_inst), 100);
                });
            } else {
                setTimeout(() => me.attach_button(report_inst), 100);
            }
            return res;
        };

        const original_refresh = QueryReportClass.prototype.refresh;
        QueryReportClass.prototype.refresh = function () {
            const res = original_refresh.apply(this, arguments);
            const report_inst = this;
            setTimeout(() => me.attach_button(report_inst), 100);
            return res;
        };
    },

    bind_route_events: function () {
        const me = this;
        frappe.router.on("change", () => {
            const route = frappe.get_route ? frappe.get_route() : [];
            if (route[0] === "query-report" || route[0] === "report") {
                const r_name = route[1];
                if (r_name && me.prompt_cache) {
                    delete me.prompt_cache[r_name];
                }
            }
            setTimeout(() => me.check_and_attach(), 300);
            setTimeout(() => me.check_and_attach(), 800);
            setTimeout(() => me.check_and_attach(), 1500);
        });

        $(document).on("ajaxComplete", () => {
            me.check_and_attach();
        });
    },

    check_and_attach: function () {
        const route = frappe.get_route ? frappe.get_route() : [];
        if (!route || !route.length) return;

        if (route[0] === "query-report" && frappe.query_report) {
            this.attach_button(frappe.query_report);
        } else if (route[0] === "report" && window.cur_list && window.cur_list.page) {
            this.attach_button_to_page(window.cur_list.page, route[1]);
        }
    },

    attach_button: function (report_instance) {
        if (!report_instance || !report_instance.page || !report_instance.page.inner_toolbar) return;
        const report_name = report_instance.report_name || (frappe.get_route ? frappe.get_route()[1] : null);
        if (!report_name) return;
        this.attach_button_to_page(report_instance.page, report_name);
    },

    attach_button_to_page: function (page, report_name) {
        if (!page || !page.inner_toolbar || !report_name) return;

        const $toolbar = $(page.inner_toolbar);
        const existing_btn = $toolbar.find(".hns-report-prompt-btn");
        if (existing_btn.length && existing_btn.attr("data-report") === report_name) {
            return;
        }

        if ($toolbar.data("hns-loading-report") === report_name) {
            return;
        }

        if (this.prompt_cache && this.prompt_cache[report_name] !== undefined) {
            this.render_toolbar_button($toolbar, report_name, this.prompt_cache[report_name]);
            return;
        }

        $toolbar.data("hns-loading-report", report_name);

        frappe.call({
            method: "hns_ai_assistant_app.api.ai_handler.get_report_prompts",
            args: { report_name: report_name },
            callback: (r) => {
                $toolbar.removeData("hns-loading-report");
                const prompts = r.message || [];
                if (!this.prompt_cache) this.prompt_cache = {};
                this.prompt_cache[report_name] = prompts;
                this.render_toolbar_button($toolbar, report_name, prompts);
            },
            error: () => {
                $toolbar.removeData("hns-loading-report");
            }
        });
    },

    has_report_data: function () {
        if (frappe.query_report && frappe.query_report.data && frappe.query_report.data.length > 0) {
            return true;
        }
        if (window.cur_list && window.cur_list.data && window.cur_list.data.length > 0) {
            return true;
        }
        return false;
    },

    notify_no_data: function () {
        frappe.msgprint({
            title: __("Data Not Available"),
            indicator: "orange",
            message: __("Data is not available. Please run the report first.")
        });
        frappe.show_alert({
            message: __("Data is not available. Please run the report first."),
            indicator: "orange"
        });
    },

    render_toolbar_button: function ($toolbar, report_name, prompts) {
        $toolbar.find(".hns-report-prompt-btn").remove();

        let $btn;
        if (prompts && prompts.length > 0) {
            $btn = $(`
                <button type="button" class="btn btn-default ellipsis hns-report-prompt-btn hns-free-ai-btn" data-report="${frappe.utils.escape_html(report_name)}" data-label="Ask Gemini" title="${__("Ask Gemini about {0}", [report_name])}">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
                    </svg>
                    <span>${__("Ask Gemini")}</span>
                </button>
            `);

            $btn.on("click", (e) => {
                e.preventDefault();
                if (!this.has_report_data()) {
                    this.notify_no_data();
                    return;
                }
                this.render_dialog(report_name, prompts);
            });
        } else {
            $btn = $(`
                <button type="button" class="btn btn-default ellipsis hns-report-prompt-btn hns-add-prompt-btn" data-report="${frappe.utils.escape_html(report_name)}" data-label="Add Prompt" title="${__("Add Prompt for {0}", [report_name])}">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="12" y1="5" x2="12" y2="19"></line>
                        <line x1="5" y1="12" x2="19" y2="12"></line>
                    </svg>
                    <span>${__("Add Prompt")}</span>
                </button>
            `);

            $btn.on("click", (e) => {
                e.preventDefault();
                delete this.prompt_cache[report_name];
                if (e.ctrlKey || e.metaKey) {
                    window.open(`/app/hns-ai-assistant-app-prompt/new?report=${encodeURIComponent(report_name)}`, "_blank");
                } else {
                    frappe.new_doc("Hns AI Report Prompt", { report: report_name });
                }
            });
        }

        const $actions = $toolbar.find('.inner-group-button[data-label="Actions"], .inner-group-button');
        if ($actions.length) {
            $btn.insertBefore($actions.first());
        } else {
            $toolbar.append($btn);
        }
        $toolbar.removeClass("hide");
    },

    open_prompt_dialog: function (report_name) {
        if (!this.has_report_data()) {
            this.notify_no_data();
            return;
        }

        if (this.prompt_cache && this.prompt_cache[report_name] !== undefined) {
            this.render_dialog(report_name, this.prompt_cache[report_name]);
            return;
        }

        frappe.call({
            method: "hns_ai_assistant_app.api.ai_handler.get_report_prompts",
            args: { report_name: report_name },
            freeze: true,
            freeze_message: __("Loading AI Prompts..."),
            callback: (r) => {
                const prompts = r.message || [];
                if (!this.prompt_cache) this.prompt_cache = {};
                this.prompt_cache[report_name] = prompts;
                this.render_dialog(report_name, prompts);
            }
        });
    },

    render_dialog: function (report_name, prompts) {
        let selected_prompt_text = prompts.length > 0 ? prompts[0].prompt : "";

        let prompt_cards_html = "";
        if (prompts.length > 0) {
            prompt_cards_html = `
                <div style="font-size: 12px; font-weight: 600; color: #4b5563; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px;">
                    ${__("Available Prompts ({0})", [prompts.length])}
                </div>
                <div class="hns-prompt-list">
                    ${prompts.map((p, idx) => `
                        <div class="hns-prompt-card ${idx === 0 ? 'selected' : ''}" data-idx="${idx}">
                            <div class="hns-prompt-radio"></div>
                            <div class="hns-prompt-text-preview">${frappe.utils.escape_html(p.prompt)}</div>
                        </div>
                    `).join("")}
                </div>
            `;
        } else {
            prompt_cards_html = `
                <div style="padding: 16px; background: #f9fafb; border: 1px dashed #d1d5db; border-radius: 8px; text-align: center;">
                    <div style="font-size: 13px; color: #6b7280; margin-bottom: 8px;">
                        ${__("No prompts configured for report: <b>{0}</b>", [report_name])}
                    </div>
                    <a href="/app/hns-ai-assistant-app-prompt/new?report=${encodeURIComponent(report_name)}" target="_blank" class="btn btn-xs btn-default" style="display: inline-flex; align-items: center; gap: 4px;">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                        ${__("Add New Prompt for this Report")}
                    </a>
                </div>
            `;
        }

        const dialog_html = `
            <div class="hns-prompt-dialog-body">
                ${prompt_cards_html}

                <div>
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                        <label style="font-size: 12px; font-weight: 600; color: #4b5563; text-transform: uppercase; letter-spacing: 0.5px; margin: 0;">
                            ${__("Prompt to Ask (Editable)")}
                        </label>
                        <span style="font-size: 11px; color: #9ca3af;">${__("You can modify the prompt before submitting")}</span>
                    </div>
                    <textarea class="hns-prompt-textarea" id="hns-prompt-editor" placeholder="${__("Type or select a prompt...")}">${frappe.utils.escape_html(selected_prompt_text)}</textarea>
                </div>
            </div>
        `;

        const dialog = new frappe.ui.Dialog({
            title: `<div style="display:flex; align-items:center; gap:8px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
                </svg>
                <span>${__("Ask Gemini - {0}", [report_name])}</span>
            </div>`,
            size: "large",
            fields: [
                {
                    fieldtype: "HTML",
                    fieldname: "prompt_html",
                    options: dialog_html
                }
            ],
            primary_action_label: __("✨ Ask Gemini (with Screen Data)"),
            primary_action: () => {
                if (!this.has_report_data()) {
                    this.notify_no_data();
                    return;
                }

                const prompt_val = dialog.$wrapper.find("#hns-prompt-editor").val().trim();
                if (!prompt_val) {
                    frappe.show_alert({ message: __("Please select or enter a prompt."), indicator: "orange" });
                    return;
                }

                dialog.hide();
                this.trigger_desktop_gemini(prompt_val, report_name);
            }
        });

        dialog.add_custom_action(__("Copy Only"), () => {
            if (!this.has_report_data()) {
                this.notify_no_data();
                return;
            }

            const prompt_val = dialog.$wrapper.find("#hns-prompt-editor").val().trim();
            if (prompt_val) {
                const full_prompt = this.build_full_prompt(prompt_val, report_name);
                this.copy_to_clipboard(full_prompt);
                frappe.show_alert({ message: __("Prompt + Report Screen Data copied!"), indicator: "green" });
                dialog.hide();
            }
        });

        dialog.show();

        const $modal_actions = dialog.$wrapper.find(".modal-header .modal-actions");
        if ($modal_actions.length) {
            $modal_actions.css({
                "display": "flex",
                "align-items": "center",
                "gap": "6px"
            });
        }

        const $add_prompt_btn = $(`
            <button type="button" class="btn btn-xs hns-add-prompt-btn hns-dialog-add-prompt-btn" style="margin-right: 4px;" title="${__("Add Prompt for {0}", [report_name])}">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="12" y1="5" x2="12" y2="19"></line>
                    <line x1="5" y1="12" x2="19" y2="12"></line>
                </svg>
                <span>${__("Add Prompt")}</span>
            </button>
        `);

        const $close_btn = dialog.$wrapper.find(".modal-header .btn-modal-close, .modal-header [data-dismiss='modal']");
        if ($close_btn.length) {
            $close_btn.before($add_prompt_btn);
        } else if ($modal_actions.length) {
            $modal_actions.append($add_prompt_btn);
        } else {
            dialog.$wrapper.find(".modal-header").append($add_prompt_btn);
        }

        $add_prompt_btn.on("click", (e) => {
            e.preventDefault();
            if (e.ctrlKey || e.metaKey) {
                delete this.prompt_cache[report_name];
                window.open(`/app/hns-ai-assistant-app-prompt/new?report=${encodeURIComponent(report_name)}`, "_blank");
                return;
            }
            this.prompt_new_dialog(report_name, dialog);
        });

        // Bind prompt card selection
        dialog.$wrapper.find(".hns-prompt-card").on("click", function () {
            dialog.$wrapper.find(".hns-prompt-card").removeClass("selected");
            $(this).addClass("selected");
            const idx = parseInt($(this).attr("data-idx"), 10);
            if (prompts[idx]) {
                dialog.$wrapper.find("#hns-prompt-editor").val(prompts[idx].prompt);
            }
        });
    },

    prompt_new_dialog: function (report_name, parent_dialog) {
        const d = new frappe.ui.Dialog({
            title: `<div style="display:flex; align-items:center; gap:8px;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="12" y1="5" x2="12" y2="19"></line>
                    <line x1="5" y1="12" x2="19" y2="12"></line>
                </svg>
                <span>${__("Add Prompt - {0}", [report_name])}</span>
            </div>`,
            fields: [
                {
                    fieldname: "report",
                    fieldtype: "Link",
                    options: "Report",
                    label: __("Report"),
                    default: report_name,
                    read_only: 1
                },
                {
                    fieldname: "prompt",
                    fieldtype: "Small Text",
                    label: __("Prompt"),
                    description: __("Enter the reusable AI analysis prompt for this report.")
                }
            ],
            primary_action_label: __("Save Prompt"),
            primary_action: () => {
                const prompt_input = d.fields_dict.prompt;
                const prompt_text = (prompt_input ? prompt_input.get_value() : "").trim();

                if (!prompt_text) {
                    show_prompt_error(__("Prompt is required. Please enter a prompt."));
                    return;
                }
                clear_prompt_error();

                frappe.call({
                    method: "hns_ai_assistant_app.api.ai_handler.add_report_prompt",
                    args: {
                        report_name: report_name,
                        prompt: prompt_text
                    },
                    freeze: true,
                    freeze_message: __("Saving Prompt..."),
                    callback: (r) => {
                        if (!r.exc) {
                            frappe.show_alert({ message: __("Prompt added successfully!"), indicator: "green" });
                            if (this.prompt_cache) {
                                delete this.prompt_cache[report_name];
                            }
                            d.hide();
                            if (parent_dialog) {
                                parent_dialog.hide();
                            }
                            this.open_prompt_dialog(report_name);
                        }
                    }
                });
            }
        });

        const $prompt_wrapper = d.fields_dict.prompt.$wrapper;
        const $prompt_textarea = $prompt_wrapper.find("textarea");

        $prompt_wrapper.find("label.control-label").append(' <span class="text-danger">*</span>');

        const clear_prompt_error = () => {
            $prompt_wrapper.find(".hns-dialog-error-msg").remove();
            $prompt_textarea.css({
                "border-color": "",
                "box-shadow": ""
            });
        };

        const show_prompt_error = (msg) => {
            clear_prompt_error();
            $prompt_textarea.css({
                "border-color": "#ef4444",
                "box-shadow": "0 0 0 1px #ef4444"
            });
            $prompt_wrapper.append(`
                <div class="hns-dialog-error-msg" style="color: #ef4444; font-size: 12px; margin-top: 6px; display: flex; align-items: center; gap: 4px;">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="12" y1="8" x2="12" y2="12"></line>
                        <line x1="12" y1="16" x2="12.01" y2="16"></line>
                    </svg>
                    <span>${frappe.utils.escape_html(msg)}</span>
                </div>
            `);
            $prompt_textarea.focus();
        };

        $prompt_textarea.on("input keyup change", () => {
            clear_prompt_error();
        });

        d.show();
    },

    build_full_prompt: function (prompt_val, report_name) {
        const context = this.get_report_screen_context(report_name);
        return context ? `${prompt_val}\n\n${context}` : prompt_val;
    },

    get_report_screen_context: function (report_name) {
        try {
            if (!frappe.query_report) return "";
            const qr = frappe.query_report;
            if (!qr.data || !qr.data.length) return "";

            const filters = qr.get_filter_values ? qr.get_filter_values() : {};
            const filter_entries = Object.entries(filters)
                .filter(([k, v]) => v !== null && v !== undefined && v !== "" && v !== false)
                .map(([k, v]) => `${k}: ${v}`);

            const all_cols = qr.columns || [];
            const cols = all_cols
                .map((c, original_idx) => {
                    let label = "";
                    let fieldname = "";
                    if (typeof c === "string") {
                        const parts = c.split(":");
                        label = parts[0];
                        fieldname = parts[0];
                    } else if (typeof c === "object" && c !== null) {
                        label = c.label || c.fieldname || "";
                        fieldname = c.fieldname || c.label || "";
                    }
                    return { label, fieldname, idx: original_idx };
                })
                .filter(c => c.label && !c.label.startsWith("_") && c.fieldname !== "_user_tags")
                .slice(0, 8);

            if (!cols.length) return "";

            const header_row = "| " + cols.map(c => c.label).join(" | ") + " |";
            const separator_row = "| " + cols.map(() => "---").join(" | ") + " |";

            const data_rows = [];

            for (let i = 0; i < qr.data.length; i++) {
                const row = qr.data[i];
                if (!row) continue;

                const cells = cols.map(c => {
                    let val = "";
                    if (Array.isArray(row)) {
                        val = row[c.idx] !== undefined && row[c.idx] !== null ? row[c.idx] : "";
                    } else if (typeof row === "object" && row !== null) {
                        val = row[c.fieldname] !== undefined ? row[c.fieldname] : (row[c.label] !== undefined ? row[c.label] : "");
                    }
                    if (val === null || val === undefined) val = "";
                    if (typeof val === "number") val = Number(val).toLocaleString();
                    val = String(val).replace(/\|/g, "/").replace(/[\r\n]+/g, " ").trim();
                    return val.length > 30 ? val.substring(0, 27) + "..." : val;
                });
                data_rows.push("| " + cells.join(" | ") + " |");
            }

            let context_md = `--- 📊 REPORT SCREEN DATA (${qr.data.length} total rows) ---\n`;
            context_md += `Report: ${report_name || qr.report_name || "Query Report"}\n`;
            if (filter_entries.length) {
                context_md += `Active Filters: ${filter_entries.join(", ")}\n`;
            }
            context_md += `\n${header_row}\n${separator_row}\n${data_rows.join("\n")}\n`;
            context_md += `--------------------------------------------------`;
            return context_md;
        } catch (e) {
            console.warn("Failed to extract report context:", e);
            return "";
        }
    },

    get_report_csv_data: function (report_name) {
        try {
            if (!frappe.query_report || !frappe.query_report.data || !frappe.query_report.data.length) return "";
            const qr = frappe.query_report;
            const cols = (qr.columns || []).map((c, idx) => {
                let label = "";
                let fieldname = "";
                if (typeof c === "string") {
                    label = c.split(":")[0];
                    fieldname = label;
                } else if (typeof c === "object" && c !== null) {
                    label = c.label || c.fieldname || "";
                    fieldname = c.fieldname || c.label || "";
                }
                return { label, fieldname, idx };
            }).filter(c => c.label && !c.label.startsWith("_") && c.fieldname !== "_user_tags");

            if (!cols.length) return "";

            const escape_csv_cell = (val) => {
                if (val === null || val === undefined) return '""';
                let str = String(val).replace(/"/g, '""');
                return `"${str}"`;
            };

            const header_line = cols.map(c => escape_csv_cell(c.label)).join(",");
            const rows = [];
            for (let i = 0; i < qr.data.length; i++) {
                const row = qr.data[i];
                if (!row) continue;
                const line = cols.map(c => {
                    let val = "";
                    if (Array.isArray(row)) {
                        val = row[c.idx] !== undefined && row[c.idx] !== null ? row[c.idx] : "";
                    } else if (typeof row === "object" && row !== null) {
                        val = row[c.fieldname] !== undefined ? row[c.fieldname] : (row[c.label] !== undefined ? row[c.label] : "");
                    }
                    return escape_csv_cell(val);
                }).join(",");
                rows.push(line);
            }
            return [header_line, ...rows].join("\r\n");
        } catch (e) {
            console.warn("Failed to generate CSV data:", e);
            return "";
        }
    },

    trigger_desktop_gemini: function (prompt_val, report_name) {
        if (!this.has_report_data()) {
            this.notify_no_data();
            return;
        }

        const me = this;
        const full_prompt = this.build_full_prompt(prompt_val, report_name);
        const csv_data = this.get_report_csv_data(report_name);

        // 1. Copy prompt and full report table to clipboard
        me.copy_to_clipboard(full_prompt);

        // 2. Dispatch custom event to Chrome Extension to open the native Side Panel
        window.postMessage({
            type: "HNS_OPEN_GEMINI_SIDEPANEL",
            prompt: full_prompt,
            report_name: report_name,
            attachment: csv_data ? {
                filename: `${(report_name || "Report").replace(/[^a-zA-Z0-9_-]/g, "_")}.csv`,
                content: csv_data,
                mime_type: "text/csv"
            } : null
        }, "*");

        const is_extension_installed = document.documentElement.getAttribute("data-gemini-sidepanel-installed") === "true";

        if (is_extension_installed) {
            frappe.show_alert({
                message: __("✨ Gemini Side Panel opened with report data!"),
                indicator: "green"
            }, 4);
        } else {
            const sw = window.screen.availWidth || 1366;
            const sh = window.screen.availHeight || 768;
            const sidebar_w = Math.min(500, Math.max(420, Math.floor(sw * 0.38)));
            const sidebar_h = Math.max(580, sh - 60);
            const pos_x = Math.max(0, sw - sidebar_w - 10);
            const pos_y = 30;
            const gemini_url = "https://gemini.google.com/app";

            window.open(
                gemini_url,
                "GeminiSidebar",
                `width=${sidebar_w},height=${sidebar_h},top=${pos_y},left=${pos_x},resizable=yes,scrollbars=yes,status=no,location=no,toolbar=no,menubar=no`
            );

            frappe.show_alert({
                message: __("✨ Gemini window opened! Auto-pasting report screen data..."),
                indicator: "green"
            }, 4);
        }
    },

    copy_to_clipboard: function (text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).catch(() => {
                this.fallback_copy(text);
            });
        } else {
            this.fallback_copy(text);
        }
    },

    fallback_copy: function (text) {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        try {
            document.execCommand("copy");
        } catch (e) {
            // ignore
        }
        document.body.removeChild(ta);
    },

    show_gemini_guide: function (report_name, prompt) {
        $(".hns-gemini-guide").remove();

        const guide = $(`
            <div class="hns-gemini-guide">
                <div class="hns-guide-header">
                    <div class="hns-guide-title">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
                        </svg>
                        <span>${__("Prompt Copied to Clipboard!")}</span>
                    </div>
                </div>
                <div class="hns-guide-content">
                    <p style="margin: 0 0 6px 0;">
                        ${__("Prompt copied to clipboard. You can paste it into Gemini (<kbd class='hns-guide-kbd'>Ctrl + V</kbd>).")}
                    </p>
                </div>
                <div class="hns-guide-dismiss">
                    <button type="button" class="btn-guide-close">${__("Got it!")}</button>
                </div>
            </div>
        `);

        guide.find(".btn-guide-close").on("click", () => {
            guide.fadeOut(200, () => guide.remove());
        });

        $("body").append(guide);

        setTimeout(() => {
            if (guide.length && guide.parent().length) {
                guide.fadeOut(500, () => guide.remove());
            }
        }, 5000);
    }
};

$(document).ready(function () {
    hns_ai_assistant_app.ReportPrompt.init();

    if (frappe.boot && frappe.boot.user && frappe.boot.user.can_read && 
        !frappe.boot.user.can_read.includes("Hns AI Assistant App Setting")) {
        return;
    }
    
    hns_ai_assistant_app.Assistant.init();
});