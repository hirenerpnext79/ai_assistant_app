import frappe



def add_ask_akansha_to_help_dropdown():
    try:
        navbar_settings = frappe.get_single("Navbar Settings")
        item_label = "Ask Akansha"
        action = "jQuery('#ask-akansha-btn').click()"
        
        navbar_item = None
        for item in navbar_settings.help_dropdown:
            if item.item_label == item_label or item.action == action:
                navbar_item = item
                break
        
        if navbar_item:
            navbar_item.item_label = item_label
            navbar_item.item_type = "Action"
            navbar_item.action = action
            navbar_item.hidden = 0
            navbar_item.is_standard = 1
        else:
            navbar_settings.append(
                "help_dropdown",
                {
                    "item_label": item_label,
                    "item_type": "Action",
                    "action": action,
                    "is_standard": 1,
                    "hidden": 0,
                },
            )
        
        navbar_settings.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(title="Failed to setup Ask Akansha in Navbar Settings")
        raise


def execute():
    add_ask_akansha_to_help_dropdown()
