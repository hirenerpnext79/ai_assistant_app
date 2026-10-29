// content.js - Injected into ERPNext webpage to bridge window messages to extension

window.addEventListener("message", (event) => {
    if (event.source !== window) return;
    if (event.data && event.data.type === "HNS_OPEN_GEMINI_SIDEPANEL") {
        try {
            chrome.runtime.sendMessage({
                type: "OPEN_GEMINI_SIDEPANEL",
                prompt: event.data.prompt || ""
            });
        } catch (e) {
            console.warn("[HNS Extension] Bridge error:", e);
        }
    }
});

document.documentElement.setAttribute("data-gemini-sidepanel-installed", "true");

