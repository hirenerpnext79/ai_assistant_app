frappe.listview_settings["HNS AI Assistant App Prompt"] = {
    onload: function (listview) {
        const btn = listview.page.add_inner_button(__("Download Extension"), function () {
            window.open("/api/method/hns_ai_assistant_app.api.ai_handler.download_chrome_extension");
        });
        btn.addClass("btn-primary");
        btn.prepend(`<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 5px; vertical-align: -2px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>`);
    }
};

