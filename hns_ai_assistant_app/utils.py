import frappe
import json
from frappe.utils import now, today

SETTINGS_DOCTYPE = "Hns AI Assistant App Setting"


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

    def query_erpnext_data(
        self,
        doctype: str,
        fields: list,
        filters,
        operation: str = "list",
        order_by: str = None,
        limit: int = None,
        offset: int = 0,
        sum_field: str = None
    ) -> dict:

        try:
            self._check_doctype_access(doctype)

            meta = frappe.get_meta(doctype)

            valid_fields = {
                df.fieldname
                for df in meta.fields
                if df.fieldname
            }

            valid_fields.update({
                "name",
                "owner",
                "creation",
                "modified",
                "modified_by",
                "docstatus",
                "idx"
            })

            if not fields:
                raise ValueError(
                    f"No fields specified for DocType '{doctype}'."
                )

            if fields == ["*"]:
                safe_fields = ["*"]
            else:
                invalid_fields = [
                    field for field in fields
                    if field not in valid_fields
                ]

                if invalid_fields:
                    raise ValueError(
                        f"Invalid field(s) {invalid_fields} "
                        f"for DocType '{doctype}'. "
                        f"Available fields: {sorted(valid_fields)}"
                    )

                safe_fields = fields

            if operation == "sum":
                if not sum_field:
                    raise ValueError(
                        "sum_field is required when operation='sum'."
                    )

                if sum_field not in valid_fields:
                    raise ValueError(
                        f"Invalid sum field '{sum_field}' "
                        f"for DocType '{doctype}'. "
                        f"Available fields: {sorted(valid_fields)}"
                    )

            parsed_filters = self._parse_filters(filters)

            self._validate_filter_fields(
                parsed_filters,
                valid_fields,
                doctype
            )

            safe_order_by = self._validate_order_by(
                order_by,
                valid_fields,
                doctype
            )

            if meta.issingle:
                data = self._query_single_doctype(
                    doctype,
                    safe_fields
                )

            elif operation == "count":
                count = frappe.db.count(
                    doctype,
                    filters=parsed_filters
                )

                data = [
                    {
                        "count": count
                    }
                ]

            elif operation == "sum":
                data = self._query_sum(
                    doctype,
                    parsed_filters,
                    sum_field
                )

            else:
                safe_limit = frappe.utils.cint(limit) if limit is not None else None
                safe_offset = frappe.utils.cint(offset) if offset is not None else 0

                query_args = {
                    "doctype": doctype,
                    "filters": parsed_filters,
                    "fields": safe_fields,
                    "order_by": safe_order_by,
                    "limit_page_length": safe_limit or 0,
                }

                if safe_offset:
                    query_args["limit_start"] = safe_offset

                data = frappe.get_all(**query_args)

            data = json.loads(
                frappe.as_json(data)
            )

            self.captured_data.append({
                "doctype": doctype,
                "operation": operation,
                "data": data
            })

            return {
                "data": data
            }

        except Exception as e:
            error_msg = str(e)

            self.captured_data.append({
                "doctype": doctype,
                "error": error_msg
            })

            return {
                "error": error_msg
            }

    def _validate_filter_fields(
        self,
        filters,
        valid_fields,
        doctype
    ):
        if not filters:
            return

        if isinstance(filters, dict):
            for field in filters.keys():
                if field not in valid_fields:
                    raise ValueError(
                        f"Invalid filter field '{field}' "
                        f"for DocType '{doctype}'. "
                        f"Available fields: {sorted(valid_fields)}"
                    )
            return

        if isinstance(filters, list):
            for condition in filters:
                if not isinstance(condition, (list, tuple)):
                    continue

                if len(condition) >= 1:
                    field = condition[0]
                    if field not in valid_fields:
                        raise ValueError(
                            f"Invalid filter field '{field}' "
                            f"for DocType '{doctype}'. "
                            f"Available fields: {sorted(valid_fields)}"
                        )

    def _validate_order_by(self, order_by, valid_fields, doctype):
        if not order_by:
            return None

        cleaned_clauses = []
        raw_clauses = [c.strip() for c in str(order_by).split(",") if c.strip()]

        for clause in raw_clauses:
            tokens = clause.strip().split()
            if not tokens:
                continue

            last_token_clean = tokens[-1].strip("` \t\r\n,;.").lower()
            direction = ""

            if last_token_clean in ("desc", "descending", "decending"):
                direction = "desc"
                field_expr = " ".join(tokens[:-1]) if len(tokens) > 1 else ""
            elif last_token_clean in ("asc", "ascending"):
                direction = "asc"
                field_expr = " ".join(tokens[:-1]) if len(tokens) > 1 else ""
            elif len(tokens) > 1:
                raise ValueError(
                    f"Invalid order direction '{tokens[-1]}'. Use 'asc' or 'desc'."
                )
            else:
                field_expr = tokens[0]

            field = field_expr.strip("` \t\r\n").split(".")[-1].strip("`")

            if not field or field not in valid_fields:
                raise ValueError(
                    f"Invalid order_by field '{field or field_expr}' for DocType '{doctype}'. "
                    f"Available fields: {sorted(valid_fields)}"
                )

            cleaned_clauses.append(f"{field} {direction}".strip())

        return ", ".join(cleaned_clauses) if cleaned_clauses else None

    def get_system_prompt(self, provider_doc=None):
        try:
            doctypes = self._get_doctype_list_str(provider_doc)
            prompt = provider_doc.system_prompt if provider_doc and provider_doc.system_prompt else ""
            today_date = today()
            
            prompt = prompt.replace('{doctype_list_str}', doctypes)
            prompt = prompt.replace('{today_date}', today_date)

            limit_rule = (
                "\n\n==================================================\n"
                "LIMIT, RANKING & TOP N QUERY RULES\n"
                "==================================================\n"
                "1. If the user specifies a number or limit (e.g. 'top 10', '10 Sales Invoice Party', 'first 5', 'limit 10'):\n"
                "   - You MUST set `limit` to that exact number (e.g. 10) in `query_erpnext_data`.\n"
                "   - All queries for that request must only use that limit.\n"
                "   - NEVER query a larger limit (such as 100 or 1000), do NOT query count, and NEVER paginate (offset) to fetch all records.\n"
                "   - Run ONLY the single query with `limit: N` and answer immediately from the returned data.\n\n"
                "2. SORTING & ORDER BY:\n"
                "   - For 'top N', 'highest', 'most', or descending queries: ALWAYS set `order_by` in descending mode (e.g. `order_by='grand_total desc'`).\n"
                "   - Check user query words for sorting direction:\n"
                "     * If 'ascending', 'asc', 'lowest', 'bottom': use 'asc' (e.g. `order_by='grand_total asc'`).\n"
                "     * If 'descending', 'desc', 'highest', 'top': use 'desc' (e.g. `order_by='grand_total desc'`).\n"
                "   - In `order_by`, strictly use only 'asc' or 'desc'. Never add trailing commas (do NOT write 'desc,').\n\n"
                "3. AGGREGATED DATA FETCH (WHEN NO LIMIT IS REQUESTED):\n"
                "   - If the user did NOT ask for a limit or specific count (e.g. total sales, total count, overall summary across all data):\n"
                "   - THEN fetch all data or use operation 'count' or 'sum' to calculate the full aggregation and give the response.\n"
            )
            if "LIMIT, RANKING & TOP N QUERY RULES" not in prompt:
                prompt += limit_rule

            if doctypes and doctypes != "All ERPNext DocTypes" and not doctypes.startswith("None"):
                doctypes_br = "<br>".join(doctypes.split("\n"))
                rule = (
                    "\n\n==================================================\n"
                    "ACCESSIBLE DOCTYPES RESTRICTION\n"
                    "==================================================\n"
                    "You only have permission to access the Available DocTypes listed above.\n"
                    "If the user asks for data, records, lists, counts, or information about any DocType that is NOT in the Available DocTypes list (such as Customer, Sales Invoice, etc.), you must NOT query external databases, you must NOT invent records, write SQL, or offer generic sample data.\n"
                    "You must respond strictly in this exact format with a new line (<br>) for each DocType:\n\n"
                    "The {DocType} DocType is not available among the accessible DocTypes. The available DocTypes are:<br><br>"
                    f"{doctypes_br}\n"
                )
                prompt += rule

            return prompt
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Hns AI Assistant: get_system_prompt error")
            return "You are a helpful assistant."

    def _check_doctype_access(self, doctype: str):
        from hns_ai_assistant_app.api.ai_handler import check_doctype_permission
        is_allowed, msg = check_doctype_permission(self.provider_doc, doctype)
        if not is_allowed:
            frappe.throw(msg)

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

    def _query_sum(
        self,
        doctype: str,
        filters,
        sum_field: str
    ) -> list:

        result = frappe.get_all(
            doctype,
            filters=filters,
            fields=[
                f"sum(`{sum_field}`) as total"
            ]
        )

        total = 0

        if result and result[0].get("total") is not None:
            total = result[0].get("total")

        return [
            {
                "sum": total
            }
        ]

    def _get_doctype_list_str(self, provider_doc) -> str:
        try:
            from hns_ai_assistant_app.api.ai_handler import get_all_allowed_doctypes
            allowed_doctypes = get_all_allowed_doctypes(provider_doc)
            
            if not allowed_doctypes:
                return "None (You currently do not have access to any DocTypes. If the user asks for data, tell them they must configure the Allowed DocTypes table first.)"
                
            if "*" in allowed_doctypes:
                return "All ERPNext DocTypes"
                
            return "\n".join(sorted(allowed_doctypes))
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Hns AI Assistant: _get_doctype_list_str error")
            return f"Error retrieving doctypes: {str(e)}"
