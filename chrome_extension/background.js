// background.js - Service worker to open side panel, omnibox auto-post, and route prompt data

chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});

// 1. Omnibox feature: Type "gem", press Tab or Space, type prompt, press Enter
chrome.omnibox.onInputEntered.addListener((text, disposition) => {
    if (!text || !text.trim()) return;

    const promptText = text.trim();

    // Store pending prompt for auto-posting
    chrome.storage.local.set({
        pendingAutoPost: promptText,
        pendingTimestamp: Date.now(),
        lastPrompt: promptText,
        timestamp: Date.now()
    });

    const targetUrl = `https://gemini.google.com/app?prompt=${encodeURIComponent(promptText)}`;

    if (disposition === "currentTab") {
        chrome.tabs.update({ url: targetUrl });
    } else {
        chrome.tabs.create({ url: targetUrl, active: true });
    }
});

chrome.omnibox.onInputChanged.addListener((text, suggest) => {
    if (!text) return;
    suggest([
        { content: text, description: `Ask Gemini: <match>${text}</match>` }
    ]);
});

// 2. Runtime messaging for Side Panel opening from ERPNext
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message && message.type === "OPEN_GEMINI_SIDEPANEL") {
        if (sender && sender.tab && sender.tab.id) {
            chrome.sidePanel.open({ tabId: sender.tab.id }).catch((err) => {
                console.warn("[SidePanel] Failed to open by tabId, trying windowId:", err);
                if (sender.tab.windowId) {
                    chrome.sidePanel.open({ windowId: sender.tab.windowId }).catch((e) => console.error(e));
                }
            });
        }

        if (message.prompt || message.attachment) {
            chrome.storage.local.set({
                lastPrompt: message.prompt || "",
                lastAttachment: message.attachment || null,
                timestamp: Date.now(),
                pendingAutoPost: message.prompt || "",
                pendingAttachment: message.attachment || null,
                pendingTimestamp: Date.now()
            });
        }

        sendResponse({ success: true });
        return true;
    }
});
