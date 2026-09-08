import frappe
import json
from frappe.utils import now

SETTINGS_DOCTYPE = "AI Assistant App Setting"


class ERPNextTools:
    def __init__(self):
        self.captured_data = []
        self.provider_doc = None

    def is_erpnext_context_enabled(self, enable_context_override=None):
        if enable_context_override is not None:
            return int(enable_context_override) == 1
        return bool(frappe.db.get_single_value(SETTINGS_DOCTYPE, "enable_erpnext_context"))

    def set_provider(self, provider_doc):
        self.provider_doc = provider_doc

    def get_query_tool_schema(self):
        schema_str = frappe.db.get_single_value(SETTINGS_DOCTYPE, "query_tool_schema")
        if not schema_str:
            return {}
        try:
            return frappe.parse_json(schema_str)
        except Exception:
            frappe.log_error(title="Invalid Tool Schema JSON", message=schema_str)
            return {}

    def query_erpnext_data(self, doctype: str, fields: list, filters,
                           operation: str = "list", order_by: str = None,
                           limit: int = None, sum_field: str = None) -> dict:
        try:
            self._check_doctype_access(doctype)
            parsed_filters = self._parse_filters(filters)

            if frappe.get_meta(doctype).issingle:
                data = self._query_single_doctype(doctype, fields)
            elif operation == "count":
                data = [{"count": frappe.db.count(doctype, filters=parsed_filters)}]
            elif operation == "sum" and sum_field:
                data = self._query_sum(doctype, parsed_filters, sum_field)
            else:
                data = frappe.get_all(
                    doctype,
                    filters=parsed_filters,
                    fields=fields,
                    order_by=order_by,
                    limit=limit or 0
                )

            data = json.loads(frappe.as_json(data))
            self.captured_data.append({"doctype": doctype, "data": data})
            return {"data": data}

        except Exception as e:
            error_msg = str(e)
            self.captured_data.append({"doctype": doctype, "error": error_msg})
            return {"error": error_msg}

    def get_system_prompt(self, provider_doc=None):
        doctypes = self._get_doctype_list_str(provider_doc)
        prompt = getattr(provider_doc, "system_prompt", "") if provider_doc else ""
        
        return f"{prompt.replace('{doctype_list_str}', doctypes)}\n\n[System Note: The current date and time is {now()}. Use this as the reference point for any relative date filters (e.g., 'last month', 'today', 'yesterday').]"

    def _check_doctype_access(self, doctype: str):
        allowed = {d.document_type for d in getattr(self.provider_doc, "allowed_doctypes", [])} if self.provider_doc else set()
        
        if doctype not in allowed:
            raise PermissionError(f"Access Denied: The AI is not permitted to query the '{doctype}' DocType. Please add it to the Allowed DocTypes table.")

        from ai_assistant_app.api.ai_handler import check_doctype_permission
        is_allowed, msg = check_doctype_permission(self.provider_doc, doctype)
        if not is_allowed:
            raise PermissionError(msg)

    def _parse_filters(self, filters):
        if isinstance(filters, (dict, list)):
            return filters
        if isinstance(filters, str) and filters:
            try:
                return frappe.parse_json(filters)
            except Exception:
                pass
        return {}

    def _query_single_doctype(self, doctype: str, fields: list) -> list:
        doc = frappe.get_single(doctype).as_dict()
        if fields and fields != ["*"]:
            return [{f: doc.get(f) for f in fields}]
        return [doc]

    def _query_sum(self, doctype: str, filters, sum_field: str) -> list:
        clean_field = "".join(c for c in sum_field if c.isalnum() or c == '_')
        result = frappe.get_all(doctype, filters=filters, fields=[f"sum(`{clean_field}`) as total"])
        return [{"sum": result[0].total if result else 0}]

    def _get_doctype_list_str(self, provider_doc) -> str:
        if provider_doc and provider_doc.allowed_doctypes:
            return ", ".join(d.document_type for d in provider_doc.allowed_doctypes)
        return "None (You currently do not have access to any DocTypes. If the user asks for data, tell them they must configure the Allowed DocTypes table first.)"
