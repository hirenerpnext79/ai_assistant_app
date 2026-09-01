// ai_assistant.js
frappe.provide("ai_assistant_app");

ai_assistant_app.Assistant = {
    init: function() {
        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "AI Assistant App Setting",
                name: "AI Assistant App Setting"
            },
            callback: (r) => {
                const settings = r.message || {};
                this.chatbot_label = settings.chatbot_label || "Ask Alexa";
                this.chatbot_icon = settings.chatbot_icon || "/assets/ai_assistant_app/images/alexa_icon.png";
                this.enable_erpnext_context = settings.enable_erpnext_context === undefined ? 1 : settings.enable_erpnext_context;
                
                this.setup_ui();
                this.bind_events();
                this.setup_menu_item();
            }
        });
    },

    setup_ui: function() {
        // Create button
        const btn = document.createElement("button");
        btn.id = "ask-alexa-btn";
        btn.innerHTML = `<img src="${this.chatbot_icon}" alt="${this.chatbot_label}">`;
        btn.title = this.chatbot_label;
        document.body.appendChild(btn);

        // Create panel
        const panel = document.createElement("div");
        panel.id = "ask-alexa-panel";
        let footer_html = "";
        if (this.enable_erpnext_context) {
            footer_html = `
            <div class="panel-footer" style="padding: 0 10px 10px 10px; font-size: 12px; display: flex; align-items: center; justify-content: flex-end; color: #6b7280; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px; background: #fff;">
                <label style="margin: 0; display: flex; align-items: center; cursor: pointer;">
                    <input type="checkbox" id="ask-alexa-enable-context" checked style="margin-right: 5px; cursor: pointer;">
                    Enable ERPNext Context
                </label>
            </div>
            `;
        }

        panel.innerHTML = `
            <div class="panel-header">
                <div class="panel-header-title">
                    <img src="${this.chatbot_icon}" class="panel-header-icon" alt="${this.chatbot_label}">
                    <span>${this.chatbot_label}</span>
                </div>
                <span class="close-btn" id="ask-alexa-close">&times;</span>
            </div>
            <div id="ask-alexa-messages">
            </div>
            <div class="panel-input-area">
                <input type="text" id="ask-alexa-input" placeholder="Ask anything..." autocomplete="off">
                <button id="ask-alexa-send">&#10148;</button>
            </div>
            ${footer_html}
        `;
        document.body.appendChild(panel);

        this.panel = document.getElementById("ask-alexa-panel");
        this.input = document.getElementById("ask-alexa-input");
        this.messages = document.getElementById("ask-alexa-messages");
        
        this.load_chat_history();
    },

    load_chat_history: function() {
        frappe.call({
            method: "ai_assistant_app.api.ai_handler.get_chat_history",
            callback: (r) => {
                if (r.message && r.message.length > 0) {
                    r.message.forEach(log => {
                        this.add_message_to_dom(log.user_query, "user", false);
                        this.add_message_to_dom(log.ai_response, "alexa", false);
                    });
                } else {
                    this.add_message_to_dom("Hello! How can I help you today?", "alexa", false);
                }
            }
        });
    },

    bind_events: function() {
        document.getElementById("ask-alexa-btn").addEventListener("click", () => this.toggle_panel());
        document.getElementById("ask-alexa-close").addEventListener("click", () => this.close_panel());
        
        document.getElementById("ask-alexa-send").addEventListener("click", () => this.send_message());
        this.input.addEventListener("keypress", (e) => {
            if (e.key === "Enter") this.send_message();
        });
    },

    toggle_panel: function() {
        this.panel.classList.toggle("active");
        if (this.panel.classList.contains("active")) {
            this.input.focus();
        }
    },

    close_panel: function() {
        this.panel.classList.remove("active");
    },

    send_message: function() {
        if (this.is_processing) return;
        
        const text = this.input.value.trim();
        if (!text) return;

        this.add_message(text, "user");
        this.input.value = "";
        
        this.is_processing = true;
        this.input.disabled = true;
        const send_btn = document.getElementById("ask-alexa-send");
        if (send_btn) send_btn.disabled = true;
        
        const enable_context_checkbox = document.getElementById("ask-alexa-enable-context");
        const enable_context = enable_context_checkbox ? enable_context_checkbox.checked : (this.enable_erpnext_context ? true : false);

        frappe.call({
            method: "ai_assistant_app.api.ai_handler.ask_alexa",
            args: {
                message: text,
                enable_context: enable_context ? 1 : 0,
                context: {
                    route: frappe.get_route ? frappe.get_route() : null
                }
            },
            callback: (r) => {
                if (r.message) {
                    this.add_message(r.message, "alexa");
                }
            },
            always: () => {
                this.is_processing = false;
                this.input.disabled = false;
                if (send_btn) send_btn.disabled = false;
                this.input.focus();
            }
        });
    },

    add_message: function(text, sender) {
        this.add_message_to_dom(text, sender, true);
    },

    add_message_to_dom: function(text, sender, save) {
        const msg = document.createElement("div");
        msg.className = `chat-message ${sender}`;
        
        if (sender === "alexa") {
            msg.innerHTML = typeof frappe.markdown !== 'undefined' ? frappe.markdown(text) : text;
            msg.style.whiteSpace = 'normal';
        } else {
            msg.textContent = text;
            msg.style.whiteSpace = 'pre-wrap';
        }
        
        this.messages.appendChild(msg);
        this.messages.scrollTop = this.messages.scrollHeight;
    },

    setup_menu_item: function() {
        if ($('#toolbar-help').length) {
            $('#toolbar-help').append(`
                <button class="btn-reset dropdown-item" id="ask-alexa-menu-item">
                    ${this.chatbot_label}
                </button>
            `);
            $('#ask-alexa-menu-item').on('click', () => {
                document.getElementById("ask-alexa-btn").classList.add("visible");
                this.panel.classList.add("active");
                this.input.focus();
            });
        }
    }
};

$(document).ready(function() {
    ai_assistant_app.Assistant.init();
});
