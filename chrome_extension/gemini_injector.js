// gemini_injector.js - Runs inside Gemini (top level or iframe) to auto-fill and auto-submit prompts

function autoAttachFile(attachment) {
    if (!attachment || !attachment.content) return;
    try {
        const file = new File([attachment.content], attachment.filename || "report.csv", {
            type: attachment.mime_type || "text/csv"
        });
        const dt = new DataTransfer();
        dt.items.add(file);

        const fileInputs = document.querySelectorAll('input[type="file"]');
        fileInputs.forEach((input) => {
            try {
                input.files = dt.files;
                input.dispatchEvent(new Event("change", { bubbles: true }));
                input.dispatchEvent(new Event("input", { bubbles: true }));
            } catch (e) {}
        });

        const dropTargets = [
            document.querySelector("rich-textarea"),
            document.querySelector("div.ql-editor"),
            document.querySelector('[contenteditable="true"]'),
            document.body
        ];

        for (const target of dropTargets) {
            if (!target) continue;
            try {
                target.dispatchEvent(new DragEvent("dragenter", { bubbles: true, cancelable: true, dataTransfer: dt }));
                target.dispatchEvent(new DragEvent("dragover", { bubbles: true, cancelable: true, dataTransfer: dt }));
                target.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: dt }));
                break;
            } catch (e) {}
        }
    } catch (e) {
        console.warn("[HNS Extension] autoAttachFile error:", e);
    }
}

function autoPostPrompt(promptText, attachment) {
    if (!promptText && !attachment) return;

    let attempts = 0;
    const maxAttempts = 50;

    const interval = setInterval(() => {
        attempts++;
        if (attempts > maxAttempts) {
            clearInterval(interval);
            return;
        }

        const editor = document.querySelector('rich-textarea div.ql-editor[contenteditable="true"]') ||
                       document.querySelector('div.ql-editor[contenteditable="true"]') ||
                       document.querySelector('[contenteditable="true"][role="textbox"]');

        if (editor) {
            editor.focus();

            if (attachment) {
                autoAttachFile(attachment);
            }

            if (promptText) {
                editor.innerHTML = `<p>${promptText.replace(/\n/g, "<br>")}</p>`;
                editor.dispatchEvent(new Event("input", { bubbles: true }));
                editor.dispatchEvent(new Event("change", { bubbles: true }));
            }

            // Wait brief moment for attachment or send button to activate
            setTimeout(() => {
                const sendBtn = document.querySelector('button[aria-label="Send message"]') ||
                                document.querySelector('button.send-button') ||
                                document.querySelector('.send-button-container button') ||
                                document.querySelector('button[mat-icon-button][aria-label*="Send"]');

                if (sendBtn && !sendBtn.disabled) {
                    sendBtn.click();
                    clearInterval(interval);
                } else {
                    const enterEvent = new KeyboardEvent("keydown", {
                        key: "Enter",
                        code: "Enter",
                        keyCode: 13,
                        which: 13,
                        bubbles: true,
                        cancelable: true
                    });
                    editor.dispatchEvent(enterEvent);
                }
            }, 400);

            clearInterval(interval);
        }
    }, 200);
}

// 1. Check if URL has ?prompt= or ?q= (e.g. from Omnibox or deep link)
const urlParams = new URLSearchParams(window.location.search);
const urlPrompt = urlParams.get("prompt") || urlParams.get("q");
if (urlPrompt) {
    autoPostPrompt(urlPrompt);
}

// 2. Check chrome.storage.local for pending prompt & attachment
if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    chrome.storage.local.get(["pendingAutoPost", "pendingAttachment", "pendingTimestamp"], (data) => {
        if (data && (data.pendingAutoPost || data.pendingAttachment)) {
            const age = Date.now() - (data.pendingTimestamp || 0);
            if (age < 60000) { // within 1 minute
                autoPostPrompt(data.pendingAutoPost, data.pendingAttachment);
                chrome.storage.local.remove(["pendingAutoPost", "pendingAttachment", "pendingTimestamp"]);
            }
        }
    });

    // Also listen for new messages sent to this frame/tab
    chrome.runtime.onMessage.addListener((msg) => {
        if (msg && msg.type === "AUTO_POST_PROMPT") {
            autoPostPrompt(msg.prompt, msg.attachment);
        }
    });
}

