// gemini_injector.js - Runs inside Gemini (top level or iframe) to auto-fill and auto-submit prompts

function autoPostPrompt(promptText) {
    if (!promptText) return;

    let attempts = 0;
    const maxAttempts = 50;

    const interval = setInterval(() => {
        attempts++;
        if (attempts > maxAttempts) {
            clearInterval(interval);
            return;
        }

        // Gemini uses div.ql-editor or rich-textarea with contenteditable="true"
        const editor = document.querySelector('rich-textarea div.ql-editor[contenteditable="true"]') ||
                       document.querySelector('div.ql-editor[contenteditable="true"]') ||
                       document.querySelector('[contenteditable="true"][role="textbox"]');

        if (editor) {
            editor.focus();
            editor.innerHTML = `<p>${promptText.replace(/\n/g, "<br>")}</p>`;
            editor.dispatchEvent(new Event("input", { bubbles: true }));
            editor.dispatchEvent(new Event("change", { bubbles: true }));

            // Wait brief moment for send button to activate
            setTimeout(() => {
                const sendBtn = document.querySelector('button[aria-label="Send message"]') ||
                                document.querySelector('button.send-button') ||
                                document.querySelector('.send-button-container button') ||
                                document.querySelector('button[mat-icon-button][aria-label*="Send"]');

                if (sendBtn && !sendBtn.disabled) {
                    sendBtn.click();
                    clearInterval(interval);
                } else {
                    // Try pressing Enter key as fallback
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
            }, 300);

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

// 2. Check chrome.storage.local for pending prompt
if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    chrome.storage.local.get(["pendingAutoPost", "pendingTimestamp"], (data) => {
        if (data && data.pendingAutoPost) {
            const age = Date.now() - (data.pendingTimestamp || 0);
            if (age < 60000) { // within 1 minute
                autoPostPrompt(data.pendingAutoPost);
                chrome.storage.local.remove(["pendingAutoPost", "pendingTimestamp"]);
            }
        }
    });

    // Also listen for new messages sent to this frame/tab
    chrome.runtime.onMessage.addListener((msg) => {
        if (msg && msg.type === "AUTO_POST_PROMPT" && msg.prompt) {
            autoPostPrompt(msg.prompt);
        }
    });
}

