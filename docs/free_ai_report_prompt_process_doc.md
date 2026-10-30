# ERPNext Reports ? Direct Gemini AI Integration (Zero Extension / No Alt+G)

## 1. Executive Summary & Core Principle

You do **NOT** need to create or install any Chrome Extension, you do **NOT** need to write or compile any Windows Native Messaging Host (`native_host.exe`), you do **NOT** need to edit the Windows Registry on every employee computer, and you do **NOT** need to simulate or press the `Alt + G` keyboard shortcut!

### Why the Chrome Extension + Native Host + `Alt+G` Approach is Impractical:
- **High Maintenance & Friction**: It requires installing Python and PyInstaller, compiling a standalone executable, editing Windows Registry keys (`HKCU\Software\Google\Chrome\NativeMessagingHosts`), and manually enabling Developer Mode on every single employee PC.
- **Fragile Keystroke Simulation**: Simulating `Alt + G` via Windows `SendInput` API requires active window focus, easily fails if the user clicks away, breaks on different keyboard layouts, and fails entirely on Mac, Linux, or mobile devices.
- **Browser Sandboxing**: Chrome does not provide any public JavaScript API for web pages to programmatically control Chrome's internal window frame controls.

---

## 2. The Recommended Direct Solution: Native In-App Gemini

Your custom app `hns_ai_assistant_app` **already has Google Gemini (`gemini-3.5-flash`) active, connected, and verified as the default AI provider**!

By leveraging your existing connected Gemini engine:
1. **Zero Client Installation**: Nothing to install on client PCs. No extensions, no `.exe`, no registry entries.
2. **Zero Keyboard Shortcuts**: No `Alt + G` or simulated keystrokes needed.
3. **100% Automated on Click**:
   - The user clicks **"Ask Gemini"** on any ERPNext Report.
   - A modal displays all active prompts configured for that report in `HNS AI Assistant App Prompt`.
   - The user selects a prompt and clicks **"? Ask Gemini"**.
   - The in-app AI Assistant panel opens automatically, submits the prompt to Gemini, and displays the response formatted in Markdown with tables, summaries, and key takeaways in real time!
4. **Universal Compatibility**: Works seamlessly across Google Chrome, Microsoft Edge, Mozilla Firefox, Safari, and mobile browsers.

---

## 3. Architecture Comparison

```
? OLD / REJECTED COMPLEX WORKFLOW (Extension + Native Host):
ERPNext Report ? window.postMessage ? Chrome Extension Content Script ? Background Service Worker ? Chrome Native Messaging (Stdio) ? native_host.exe (PyInstaller) ? Windows SendInput API (Alt+G Keystroke) ? Chrome Window Focus Required ? Manual Ctrl+V Paste

? NEW DIRECT WORKFLOW (Implemented & Active):
ERPNext Report ? Click "Ask Gemini" ? Prompt Modal (HNS AI Assistant App Prompt) ? Click "? Ask Gemini" ? Direct Backend Call to Gemini (gemini-3.5-flash) ? Live Streaming AI Response in ERPNext Slide-out Panel
```

---

## 4. Configuration Guide: Adding Prompts for Reports

1. In ERPNext Awesomebar, search for **HNS AI Assistant App Prompt** (or navigate to `/app/hns-ai-assistant-app-prompt`).
2. Click **Add HNS AI Assistant App Prompt**.
3. Set the fields:
   - **Report**: Choose the report (e.g., `Item Prices`, `Stock Balance`, `General Ledger`, `Accounts Receivable`).
   - **Prompt**: Enter the reusable analysis prompt (e.g., *"Summarize pricing discrepancies between purchase and sales price lists, highlighting items with 0 valuation."*).
   - **Is Active**: Checked (`1`).
4. Click **Save**.

---

## 5. End-to-End User Experience

1. **Navigate to Report**: Open any Query Report or Script Report (e.g. **Stock > Item Prices**).
2. **Click "Ask Gemini"**: A clean, branded button appears in the toolbar directly next to **Actions**.
3. **Choose Prompt**: The modal lists all prompts configured for that report. Selecting a prompt loads it into the editable preview.
4. **Click "? Ask Gemini"**:
   - The modal automatically closes.
   - The ERPNext AI Assistant drawer slides out from the right side of the screen.
   - It submits the prompt directly to Google Gemini and streams the structured AI answer immediately.
5. **Additional Options Available**:
   - **Open Gemini Web**: Opens `https://gemini.google.com/app` in a new tab with the prompt copied to the clipboard.
   - **Copy Only**: Copies the prompt to the system clipboard for external use.

---

## 6. Implementation Technical Reference

- **Backend API**: [get_report_prompts](file:///home/hns/erpnext/apps/hns_ai_assistant_app/hns_ai_assistant_app/api/ai_handler.py#L290-L305) in `hns_ai_assistant_app/api/ai_handler.py`.
- **Frontend Controller**: `hns_ai_assistant_app.ReportPrompt` in [ai_assistant.js](file:///home/hns/erpnext/apps/hns_ai_assistant_app/hns_ai_assistant_app/public/js/ai_assistant.js#L490-L750).
- **Styles**: [ai_assistant.css](file:///home/hns/erpnext/apps/hns_ai_assistant_app/hns_ai_assistant_app/public/css/ai_assistant.css#L614-L780).
