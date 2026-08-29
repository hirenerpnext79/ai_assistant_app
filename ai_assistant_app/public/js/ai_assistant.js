// ai_assistant.js
frappe.provide("ai_assistant_app");

ai_assistant_app.Assistant = {
    init: function() {
        this.setup_ui();
        this.bind_events();
        this.setup_menu_item();
    },

    setup_ui: function() {
        // Create button
        const btn = document.createElement("button");
        btn.id = "ask-alexa-btn";
        btn.innerHTML = '<img src="/assets/ai_assistant_app/images/alexa_icon.png" alt="Ask Alexa">';
        btn.title = "Ask Alexa";
        document.body.appendChild(btn);

        // Create panel
        const panel = document.createElement("div");
        panel.id = "ask-alexa-panel";
        panel.innerHTML = `
            <div class="panel-header">
                <div class="panel-header-title">
                    <img src="/assets/ai_assistant_app/images/alexa_icon.png" class="panel-header-icon" alt="Alexa">
                    <span>Ask Alexa</span>
                </div>
                <span class="close-btn" id="ask-alexa-close">&times;</span>
            </div>
            <div id="ask-alexa-messages">
            </div>
            <div class="panel-input-area">
                <input type="text" id="ask-alexa-input" placeholder="Ask anything..." autocomplete="off">
                <button id="ask-alexa-send">&#10148;</button>
            </div>
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
        const text = this.input.value.trim();
        if (!text) return;

        this.add_message(text, "user");
        this.input.value = "";
        
        frappe.call({
            method: "ai_assistant_app.api.ai_handler.ask_alexa",
            args: {
                message: text,
                context: {
                    route: frappe.get_route ? frappe.get_route() : null
                }
            },
            callback: (r) => {
                if (r.message) {
                    this.add_message(r.message, "alexa");
                }
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
                    Ask Alexa
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
