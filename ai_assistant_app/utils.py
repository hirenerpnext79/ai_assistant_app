import frappe
import json

SETTINGS_DOCTYPE = "AI Assistant App Setting"


class ERPNextTools:
    def __init__(self):
        self.captured_data = []
        self.provider_doc = None

    def is_erpnext_context_enabled(self, enable_context_override=None):
        if enable_context_override is not None:
            return int(enable_context_override) == 1
        return frappe.db.get_single_value(SETTINGS_DOCTYPE, "enable_erpnext_context") == 1

    def set_provider(self, provider_doc):
        self.provider_doc = provider_doc

    def get_query_tool_schema(self):
        schema_str = frappe.db.get_single_value(SETTINGS_DOCTYPE, "query_tool_schema")
        if not schema_str:
            return {}
        try:
            return json.loads(schema_str)
        except json.JSONDecodeError:
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
                count = frappe.db.count(doctype, filters=parsed_filters)
                data = [{"count": count}]
            elif operation == "sum" and sum_field:
                data = self._query_sum(doctype, parsed_filters, sum_field)
            else:
                data = self._query_list(doctype, parsed_filters, fields, order_by, limit)

            data = json.loads(frappe.as_json(data))
            self.captured_data.append({"doctype": doctype, "data": data})
            return {"data": data}

        except Exception as e:
            error_msg = str(e)
            self.captured_data.append({"doctype": doctype, "error": error_msg})
            return {"error": error_msg}

    def get_system_prompt(self, provider_doc=None):
        doctype_list_str = self._get_doctype_list_str(provider_doc)
        custom_prompt = provider_doc.system_prompt if provider_doc else ""
        return custom_prompt.replace("{doctype_list_str}", doctype_list_str)

    def _check_doctype_access(self, doctype: str):
        if not self.provider_doc or not self.provider_doc.allowed_doctypes:
            raise PermissionError(
                f"Access Denied: The AI is not permitted to query the '{doctype}' DocType. "
                "Please add it to the Allowed DocTypes table."
            )

        allowed_doctypes = {d.document_type for d in self.provider_doc.allowed_doctypes}
        if doctype not in allowed_doctypes:
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
            except json.JSONDecodeError:
                return {}
        return {}

    def _query_single_doctype(self, doctype: str, fields: list) -> list:
        doc_dict = frappe.get_single(doctype).as_dict()
        if fields and fields != ["*"]:
            return [{f: doc_dict.get(f) for f in fields}]
        return [doc_dict]

    def _query_sum(self, doctype: str, filters, sum_field: str) -> list:
        clean_field = "".join(c for c in sum_field if c.isalnum() or c == '_')
        result = frappe.get_all(
            doctype, filters=filters, fields=[f"sum(`{clean_field}`) as total"]
        )
        total = result[0].total if result else 0
        return [{"sum": total}]

    def _query_list(self, doctype: str, filters, fields: list,
                    order_by: str = None, limit: int = None) -> list:
        query_kwargs = {
            "filters": filters,
            "fields": fields,
            "limit": limit if limit is not None else 0,
        }
        if order_by:
            query_kwargs["order_by"] = order_by
        return frappe.get_all(doctype, **query_kwargs)

    def _get_doctype_list_str(self, provider_doc) -> str:
        if provider_doc and provider_doc.allowed_doctypes:
            return ", ".join(d.document_type for d in provider_doc.allowed_doctypes)
        return (
            "None (You currently do not have access to any DocTypes. "
            "If the user asks for data, tell them they must configure the Allowed DocTypes table first.)"
        )
