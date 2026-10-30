frappe.ui.form.on("HNS AI Assistant App Prompt", {
    refresh(frm) {
        frm.add_custom_button(__("Download Extension"), function () {
            window.open("/api/method/hns_ai_assistant_app.api.ai_handler.download_chrome_extension");
        });
    }
});
