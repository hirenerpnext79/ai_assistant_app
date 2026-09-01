import frappe
import json

class ERPNextTools:
    def __init__(self):
        self.captured_data = []
        self.provider_doc = None
        
    def is_erpnext_context_enabled(self, enable_context_override=None):
        if enable_context_override is not None:
            return int(enable_context_override) == 1
        return frappe.db.get_single_value("AI Assistant App Setting", "enable_erpnext_context") == 1

    def set_provider(self, provider_doc):
        self.provider_doc = provider_doc

    def get_query_tool_schema(self):
        return {
            "name": "query_erpnext_data",
            "description": "Query ERPNext data using DocType, filters and fields. Use this when the user asks for data like overdue invoices, user lists, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctype": { "type": "string" },
                    "fields": { "type": "array", "items": { "type": "string" } },
                    "filters": { "type": "string", "description": "JSON string representing a dictionary, even if empty, like '{}'" }
                },
                "required": ["doctype", "fields", "filters"]
            }
        }
        
    def query_erpnext_data(self, doctype: str, fields: list, filters: str) -> dict:
        allowed_doctypes = []
        if self.provider_doc and self.provider_doc.get("allowed_doctypes"):
            allowed_doctypes = [d.document_type for d in self.provider_doc.get("allowed_doctypes")]
            
        if not allowed_doctypes or doctype not in allowed_doctypes:
            error_msg = f"Access Denied: The AI is not permitted to query the '{doctype}' DocType. Please tell the user to add it to the Allowed DocTypes table."
            self.captured_data.append({"doctype": doctype, "error": error_msg})
            return {"error": error_msg}
            
        try:
            parsed_filters = json.loads(filters) if filters else {}
        except Exception:
            parsed_filters = {}
        
        try:
            is_single = frappe.get_meta(doctype).issingle
            if is_single:
                doc = frappe.get_single(doctype)
                doc_dict = doc.as_dict()
                if fields and fields != ["*"]:
                    data = [{f: doc_dict.get(f) for f in fields}]
                else:
                    data = [doc_dict]
            else:
                data = frappe.get_all(doctype, filters=parsed_filters, fields=fields, limit=50)
                
            data = json.loads(frappe.as_json(data))
            self.captured_data.append({"doctype": doctype, "data": data})
            return {"data": data}
        except Exception as e:
            self.captured_data.append({"doctype": doctype, "error": str(e)})
            return {"error": str(e)}

    def get_system_prompt(self, provider_doc=None):
        if provider_doc and provider_doc.get("allowed_doctypes"):
            doctype_list = [d.document_type for d in provider_doc.get("allowed_doctypes")]
            doctype_list_str = ", ".join(doctype_list)
        else:
            doctype_list_str = "None (You currently do not have access to any DocTypes. If the user asks for data, tell them they must configure the Allowed DocTypes table first.)"

        custom_prompt = provider_doc.get("system_prompt") if provider_doc else None

        if custom_prompt:
            try:
                return custom_prompt.replace("{doctype_list_str}", doctype_list_str)
            except Exception:
                return custom_prompt

        return f"You are Alexa, an ERPNext AI Assistant. You have access to a tool called query_erpnext_data to fetch data from the ERPNext database. When a user asks for information, use the tool if needed, then format the result nicely for the user. Important rule: the filters should always be a valid JSON string representing a dictionary, even if empty, like '{{}}'. And ALWAYS return actual field names for 'fields'. Here is the list of ALL valid DocTypes in the system (core and custom) to help you map the user's request: {doctype_list_str}."
