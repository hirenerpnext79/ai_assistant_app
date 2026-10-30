# ERPNext Gemini Side Panel Chrome Extension

This Chrome Extension enables opening Google Gemini in Chrome's native **Side Panel** (`chrome.sidePanel`) right from ERPNext reports and automatically passes the report prompt and screen data.

---

## 🚀 How to Install in Chrome

1. Open **Google Chrome**.
2. In the URL bar, go to:
   ```text
   chrome://extensions/
   ```
3. Enable **Developer mode** (toggle switch in the top right corner).
4. Click **Load unpacked** (button in the top left corner).
5. Select the folder:
   ```text
   \\wsl.localhost\Ubuntu\home\hns\erpnext\apps\hns_ai_assistant_app\chrome_extension
   ```
   *(Or browse via WSL: `Ubuntu` > `home` > `hns` > `erpnext` > `apps` > `hns_ai_assistant_app` > `chrome_extension`)*
6. The extension **"ERPNext Gemini Side Panel"** is now loaded!

---

## 💡 How It Works

1. Open any ERPNext Report (e.g. *Item Prices*, *General Ledger*, etc.).
2. Click the **"Ask Gemini"** button in the report toolbar.
3. Choose or customize your prompt, then click **"✨ Ask Gemini (with Screen Data)"**.
4. The extension intercepts the user click gesture via `content.js`, triggers `chrome.sidePanel.open()`, and displays the native Chrome Side Panel loaded with Gemini alongside your report data ready to copy or submit.

