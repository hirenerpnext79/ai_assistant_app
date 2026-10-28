# Copyright (c) 2026, Ai Assistant App and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class HnsAIAssistantRule(Document):
    def on_trash(self):
        frappe.throw(_("Deleting rules from Hns AI Assistant Rule is not allowed. You can deactivate this rule by unchecking 'Is Active' instead."))


@frappe.whitelist()
def get_active_rules(doctypes="", today_date="", as_list=False):
    try:
        if not frappe.db.table_exists("Hns AI Assistant Rule"):
            return [] if as_list else ""

        rule_list = frappe.get_all(
            "Hns AI Assistant Rule",
            filters={"is_active": 1},
            fields=["rule_name", "rule_prompt", "priority"],
            order_by="priority asc, creation asc"
        )
        if not rule_list:
            return [] if as_list else ""

        doctypes_br = "<br>".join(doctypes.split("\n")) if doctypes else ""

        processed_rules = []
        rule_blocks = []
        for idx, r in enumerate(rule_list, 1):
            rule_name = r.get("rule_name", "")
            rule_prompt = (r.get("rule_prompt") or "").strip()
            if "{doctype_list_str}" in rule_prompt:
                rule_prompt = rule_prompt.replace("{doctype_list_str}", doctypes)
            if "{today_date}" in rule_prompt:
                rule_prompt = rule_prompt.replace("{today_date}", today_date)
            if "{doctypes_br}" in rule_prompt:
                rule_prompt = rule_prompt.replace("{doctypes_br}", doctypes_br)

            processed_rules.append({
                "rule_name": rule_name,
                "priority": r.get("priority"),
                "rule_prompt": rule_prompt
            })
            rule_blocks.append(f"{idx}. {rule_name.upper()}\n{rule_prompt}")

        if as_list:
            return processed_rules

        return "\n\n".join(rule_blocks)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Hns AI Assistant: get_active_rules error")
        return [] if as_list else ""



