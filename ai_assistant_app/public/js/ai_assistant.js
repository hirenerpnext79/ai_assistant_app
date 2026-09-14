// ai_assistant.js
frappe.provide("ai_assistant_app");

const CHATBOT_LABEL = "Ask Akansha";

ai_assistant_app.Assistant = {
    init: function () {
        frappe.call({
            method: "frappe.client.get",
            args: { doctype: "AI Assistant App Setting", name: "AI Assistant App Setting" },
            callback: (r) => {
                const settings = r.message || {};
                this.chatbot_icon = settings.chatbot_icon || "/assets/ai_assistant_app/images/akansha_icon.png";
                this.enable_erpnext_context = settings.enable_erpnext_context === undefined ? 1 : settings.enable_erpnext_context;
                this.full_width = settings.full_width === 1;
                this.load_allowed_providers();
            }
        });
    },

    load_allowed_providers: function () {
        frappe.call({
            method: "ai_assistant_app.api.ai_handler.get_allowed_providers",
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
                this.setup_menu_item();
                
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
            method: "ai_assistant_app.api.ai_handler.get_chat_history",
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

    send_message: function () {
        if (this.is_processing) return;

        const text = this.input.value.trim();
        if (!text) return;

        this.add_message_to_dom(text, "user");
        this.input.value = "";
        const qq_wrap = document.getElementById("aak-quick-questions-wrapper");
        if (qq_wrap) qq_wrap.style.display = "none";

        this.set_processing(true);
        this.show_thinking();

        const enable_context_checkbox = document.getElementById("ask-akansha-enable-context");
        const enable_context = enable_context_checkbox
            ? enable_context_checkbox.checked
            : (this.enable_erpnext_context ? true : false);

        frappe.call({
            method: "ai_assistant_app.api.ai_handler.ask_akansha",
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

    add_message_to_dom: function (text, sender, creation = null) {
        if (!text) return;

        const wrapper = document.createElement("div");
        wrapper.className = `aak-msg-row aak-msg-${sender}`;

        const bubble = document.createElement("div");
        bubble.className = `chat-message ${sender}`;

        const content_div = document.createElement("div");
        content_div.className = "msg-content";
        if (sender === "akansha") {
            content_div.innerHTML = typeof frappe.markdown !== "undefined" ? frappe.markdown(text) : text;
        } else {
            content_div.textContent = text;
        }
        bubble.appendChild(content_div);

        const time_div = document.createElement("div");
        time_div.className = "aak-msg-time";
        const now = creation ? new Date(creation) : new Date();
        time_div.textContent = now.toLocaleTimeString([], { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
        bubble.appendChild(time_div);
        
        wrapper.appendChild(bubble);

        this.messages.appendChild(wrapper);
        this.messages.scrollTop = this.messages.scrollHeight;
    },

    setup_menu_item: function () {
        if ($("#toolbar-help").length) {
            $("#toolbar-help").append(`
                <button class="btn-reset dropdown-item" id="ask-akansha-menu-item">
                    ${CHATBOT_LABEL}
                </button>
            `);
            $("#ask-akansha-menu-item").on("click", () => {
                document.getElementById("ask-akansha-btn").classList.add("visible");
                this.panel.classList.add("active");
                this.input.focus();
            });
        }
    }
};

$(document).ready(function () {
    // Stop execution on the first line if the user doesn't have permission to read the settings
    if (frappe.boot && frappe.boot.user && frappe.boot.user.can_read && 
        !frappe.boot.user.can_read.includes("AI Assistant App Setting")) {
        return;
    }
    
    ai_assistant_app.Assistant.init();
});






