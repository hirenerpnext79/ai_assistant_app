// sidepanel.js - Direct full-height Gemini frame controller

function sendPromptToFrame(prompt) {
    if (!prompt) return;
    const frame = document.getElementById("gemini-frame");
    if (frame && frame.contentWindow) {
        try {
            frame.contentWindow.postMessage({ type: "AUTO_POST_PROMPT", prompt: prompt }, "*");
        } catch (e) {
            // Handled by gemini_injector via chrome.storage
        }
    }
}

chrome.storage.local.get(["lastPrompt", "timestamp"], (data) => {
    if (data && data.lastPrompt) {
        const age = Date.now() - (data.timestamp || 0);
        if (age < 300000) { // 5 minutes
            sendPromptToFrame(data.lastPrompt);
        }
    }
});
chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName === "local" && changes.lastPrompt && changes.lastPrompt.newValue) {
        sendPromptToFrame(changes.lastPrompt.newValue);
    }
});
