import frappe
import json

class ERPNextTools:
    def __init__(self):
        self.captured_data = []
        
    def get_query_tool(self):
        def query_erpnext_data(doctype: str, fields: list, filters: str) -> dict:
            """Query ERPNext data using DocType, filters and fields. Use this when the user asks for data like overdue invoices, user lists, etc."""
            try:
                parsed_filters = json.loads(filters) if filters else {}
            except:
                parsed_filters = {}
            
            try:
                data = frappe.get_all(doctype, filters=parsed_filters, fields=fields, limit=50)
                data = json.loads(frappe.as_json(data))
                self.captured_data.append({"doctype": doctype, "data": data})
                return {"data": data}
            except Exception as e:
                self.captured_data.append({"doctype": doctype, "error": str(e)})
                return {"error": str(e)}
                
        return query_erpnext_data

    def get_system_prompt(self, provider_doc=None):
        if provider_doc and provider_doc.get("allowed_doctypes"):
            doctype_list = [d.document_type for d in provider_doc.get("allowed_doctypes")]
            doctype_list_str = ", ".join(doctype_list)
        else:
            try:
                all_doctypes = [d.name for d in frappe.get_all("DocType", limit=2000)]
                doctype_list_str = ", ".join(all_doctypes)
            except:
                doctype_list_str = "User, Sales Invoice, Customer, Item"

        custom_prompt = provider_doc.get("system_prompt") if provider_doc else None

        if custom_prompt:
            try:
                return custom_prompt.replace("{doctype_list_str}", doctype_list_str)
            except Exception:
                return custom_prompt

        return f"You are Alexa, an ERPNext AI Assistant. You have access to a tool called query_erpnext_data to fetch data from the ERPNext database. When a user asks for information, use the tool if needed, then format the result nicely for the user. Important rule: the filters should always be a valid JSON string representing a dictionary, even if empty, like '{{}}'. And ALWAYS return actual field names for 'fields'. Here is the list of ALL valid DocTypes in the system (core and custom) to help you map the user's request: {doctype_list_str}."
