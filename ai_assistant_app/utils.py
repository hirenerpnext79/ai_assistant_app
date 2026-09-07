import frappe
import json

QUERY_TOOL_SCHEMA = {
    "name": "query_erpnext_data",
    "description": (
        "Query ERPNext/Frappe records from any DocType. "
        "Use this tool whenever the user asks to fetch, search, list, "
        "count, summarize, or filter ERPNext data. "
        "Examples: customers, suppliers, employees, users, items, "
        "sales invoices, purchase invoices, payments, stock entries, "
        "attendance, and overdue invoices."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "doctype": {
                "type": "string",
                "description": (
                    "The ERPNext/Frappe DocType to query. "
                    "Examples: Customer, Supplier, Employee, User, "
                    "Sales Invoice, Purchase Invoice, Item, Stock Entry, "
                    "Employee Checkin."
                )
            },
            "fields": {
                "type": "array",
                "description": (
                    "Fields to return from the DocType. "
                    "Use valid field names. "
                    "Include 'name' when record identity is needed."
                ),
                "items": {"type": "string"},
                "minItems": 1
            },
            "filters": {
                "type": "object",
                "description": (
                    "Filters to apply to the query. "
                    "Use {} when no filters are required. "
                    "Supported examples: "
                    "{'status': 'Submitted'}, "
                    "{'posting_date': ['>=', '2026-01-01']}, "
                    "{'posting_date': ['between', ['2026-01-01', '2026-01-31']]}, "
                    "{'status': ['in', ['Open', 'Overdue']]}, "
                    "{'customer_name': ['like', '%ABC%']}, "
                    "{'outstanding_amount': ['>', 0]}."
                ),
                "additionalProperties": True
            },
            "order_by": {
                "type": "string",
                "description": (
                    "Optional sorting expression. "
                    "Examples: 'creation desc', 'posting_date desc', 'name asc'."
                )
            },
            "limit": {
                "type": "integer",
                "description": (
                    "Maximum number of records to return. "
                    "Use a smaller value when the user asks for a sample or recent records."
                ),
                "minimum": 1,
                "maximum": 500,
                "default": 100
            }
        },
        "required": ["doctype", "fields", "filters"],
        "additionalProperties": False
    }
}

DEFAULT_SYSTEM_PROMPT_TEMPLATE = (
    "You are Alexa, an ERPNext AI Assistant with access to a tool called query_erpnext_data "
    "to fetch data from the ERPNext database. When a user asks for information, use the tool "
    "if needed, then format the result clearly for the user.\n\n"
    "Rules for building filters:\n"
    "1. The filters parameter is a JSON object (dict), NOT a string. Example: {{}}.\n"
    "2. Use the correct name field per DocType: 'employee_name' for Employee Checkin, "
    "'full_name' for User, 'customer_name' for Customer.\n"
    "3. Use 'like' for partial text: {{\"employee_name\": [\"like\", \"%John%\"]}}.\n"
    "4. Use 'between' for date/time ranges: "
    "{{\"time\": [\"between\", [\"2026-09-01 00:00:00\", \"2026-09-30 23:59:59\"]]}}.\n"
    "5. Combine multiple conditions in one filter object.\n"
    "6. Employee Checkin fields: 'employee' (ID), 'employee_name' (full name), "
    "'time' (Datetime), 'log_type' (IN/OUT), 'shift'.\n\n"
    "Available DocTypes: {doctype_list_str}."
)

STRICT_INSTRUCTION = (
    "\n\nCRITICAL RULE: You are STRICTLY an ERPNext assistant. You MUST ONLY answer questions "
    "related to ERPNext data or the ERPNext context. If the user asks a general question or "
    "requests information you cannot fetch via the tools, you MUST refuse and reply with a "
    "denied message (e.g., 'I can only assist with ERPNext data inquiries.'). "
    "Do NOT provide general knowledge answers."
)


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
        return QUERY_TOOL_SCHEMA

    def query_erpnext_data(self, doctype: str, fields: list, filters, limit: int = 50) -> dict:
        try:
            self._check_doctype_access(doctype)
            parsed_filters = self._parse_filters(filters)

            if frappe.get_meta(doctype).issingle:
                data = self._query_single_doctype(doctype, fields)
            else:
                data = frappe.get_all(doctype, filters=parsed_filters, fields=fields, limit=limit)

            data = json.loads(frappe.as_json(data))
            self.captured_data.append({"doctype": doctype, "data": data})
            return {"data": data}

        except PermissionError as e:
            error_msg = str(e)
            self.captured_data.append({"doctype": doctype, "error": error_msg})
            return {"error": error_msg}
        except Exception as e:
            self.captured_data.append({"doctype": doctype, "error": str(e)})
            return {"error": str(e)}

    def get_system_prompt(self, provider_doc=None):
        doctype_list_str = self._get_doctype_list_str(provider_doc)
        custom_prompt = provider_doc.system_prompt if provider_doc else None

        if custom_prompt:
            try:
                return custom_prompt.replace("{doctype_list_str}", doctype_list_str) + STRICT_INSTRUCTION
            except Exception:
                return custom_prompt + STRICT_INSTRUCTION

        return DEFAULT_SYSTEM_PROMPT_TEMPLATE.format(doctype_list_str=doctype_list_str) + STRICT_INSTRUCTION

    def _check_doctype_access(self, doctype: str):
        allowed_doctypes = (
            {d.document_type for d in self.provider_doc.allowed_doctypes}
            if self.provider_doc and self.provider_doc.allowed_doctypes
            else set()
        )

        if not allowed_doctypes or doctype not in allowed_doctypes:
            raise PermissionError(
                f"Access Denied: The AI is not permitted to query the '{doctype}' DocType. "
                "Please add it to the Allowed DocTypes table."
            )

        from ai_assistant_app.api.ai_handler import check_doctype_permission
        is_allowed, msg = check_doctype_permission(self.provider_doc, doctype)
        if not is_allowed:
            raise PermissionError(msg)

    def _parse_filters(self, filters) -> dict | list:
        if isinstance(filters, (dict, list)):
            return filters
        if isinstance(filters, str) and filters:
            try:
                return json.loads(filters)
            except Exception:
                return {}
        return {}

    def _query_single_doctype(self, doctype: str, fields: list) -> list:
        doc_dict = frappe.get_single(doctype).as_dict()
        if fields and fields != ["*"]:
            return [{f: doc_dict.get(f) for f in fields}]
        return [doc_dict]

    def _get_doctype_list_str(self, provider_doc) -> str:
        if provider_doc and provider_doc.allowed_doctypes:
            return ", ".join(d.document_type for d in provider_doc.allowed_doctypes)
        return (
            "None (You currently do not have access to any DocTypes. "
            "If the user asks for data, tell them they must configure the Allowed DocTypes table first.)"
        )
