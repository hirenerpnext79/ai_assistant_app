frappe.listview_settings["Hns AI Report Prompt"] = {
    onload: function (listview) {
        const btn = listview.page.add_inner_button(__("Download Extension"), function () {
            window.open("/api/method/hns_ai_assistant_app.api.ai_handler.download_chrome_extension");
        });
    }
};

