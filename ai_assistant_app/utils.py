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
        schema_str = frappe.db.get_single_value("AI Assistant App Setting", "query_tool_schema")
        if schema_str:
            try:
                return json.loads(schema_str)
            except Exception:
                pass
        return {}

    def query_erpnext_data(self, doctype: str, fields: list, filters, operation: str = "list", order_by: str = None, limit: int = None, sum_field: str = None, **kwargs) -> dict:
        try:
            self._check_doctype_access(doctype)
            parsed_filters = self._parse_filters(filters)

            if frappe.get_meta(doctype).issingle:
                data = self._query_single_doctype(doctype, fields)
            else:
                if operation == "count":
                    count = frappe.db.count(doctype, filters=parsed_filters)
                    data = [{"count": count}]
                elif operation == "sum" and sum_field:
                    clean_field = "".join(c for c in sum_field if c.isalnum() or c == '_')
                    res = frappe.get_all(doctype, filters=parsed_filters, fields=[f"sum(`{clean_field}`) as total"])
                    total = res[0].total if res else 0
                    data = [{"sum": total}]
                else:
                    query_kwargs = {"filters": parsed_filters, "fields": fields}
                    if limit is not None:
                        query_kwargs["limit"] = limit
                    else:
                        query_kwargs["limit"] = 0
                    if order_by:
                        query_kwargs["order_by"] = order_by
                    data = frappe.get_all(doctype, **query_kwargs)

            data = json.loads(frappe.as_json(data))
            print({"doctype": doctype, "data": data})
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
        custom_prompt = provider_doc.system_prompt if provider_doc else ""

        try:
            return custom_prompt.replace("{doctype_list_str}", doctype_list_str)
        except Exception:
            return custom_prompt

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



