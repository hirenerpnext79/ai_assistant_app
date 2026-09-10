import frappe
import json
from frappe.utils import now, today

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

            # ---------------------------------------------------------
            # Get actual DocType metadata
            # ---------------------------------------------------------
            meta = frappe.get_meta(doctype)

            # Actual database fields
            valid_fields = {
                df.fieldname
                for df in meta.fields
                if df.fieldname
            }

            # Standard document fields available in Frappe
            valid_fields.update({
                "name",
                "owner",
                "creation",
                "modified",
                "modified_by",
                "docstatus",
                "idx"
            })

            # ---------------------------------------------------------
            # Validate requested fields
            # ---------------------------------------------------------
            if not fields:
                raise ValueError(
                    f"No fields specified for DocType '{doctype}'."
                )

            # Allow ["*"]
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

            # ---------------------------------------------------------
            # Validate sum field
            # ---------------------------------------------------------
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

            # ---------------------------------------------------------
            # Validate filters
            # ---------------------------------------------------------
            parsed_filters = self._parse_filters(filters)

            self._validate_filter_fields(
                parsed_filters,
                valid_fields,
                doctype
            )

            # ---------------------------------------------------------
            # Validate order_by
            # ---------------------------------------------------------
            safe_order_by = self._validate_order_by(
                order_by,
                valid_fields,
                doctype
            )

            # ---------------------------------------------------------
            # Single DocType
            # ---------------------------------------------------------
            if meta.issingle:

                data = self._query_single_doctype(
                    doctype,
                    safe_fields
                )

            # ---------------------------------------------------------
            # Count
            # ---------------------------------------------------------
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

            # ---------------------------------------------------------
            # Sum
            # ---------------------------------------------------------
            elif operation == "sum":

                data = self._query_sum(
                    doctype,
                    parsed_filters,
                    sum_field
                )

            # ---------------------------------------------------------
            # List
            # ---------------------------------------------------------
            else:

                query_args = {
                    "doctype": doctype,
                    "filters": parsed_filters,
                    "fields": safe_fields,
                    "order_by": safe_order_by,
                    "limit_page_length": limit or 0,
                }

                # Pagination
                if offset:
                    query_args["limit_start"] = offset

                data = frappe.get_all(**query_args)

            # ---------------------------------------------------------
            # Convert Frappe objects to JSON-safe data
            # ---------------------------------------------------------
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
        """
        Make sure the AI never sends a filter
        using a field that does not exist.
        """

        if not filters:
            return

        # Dictionary format
        if isinstance(filters, dict):

            for field in filters.keys():

                if field not in valid_fields:

                    raise ValueError(
                        f"Invalid filter field '{field}' "
                        f"for DocType '{doctype}'. "
                        f"Available fields: {sorted(valid_fields)}"
                    )

            return

        # List format:
        #
        # [
        #   ["employee_name", "=", "Riddhi"],
        #   ["attendance_date", ">=", "2026-08-31"]
        # ]
        #
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

    def _validate_order_by(
        self,
        order_by,
        valid_fields,
        doctype
    ):
        """
        Prevent the AI from generating ORDER BY
        using a nonexistent field.
        """

        if not order_by:
            return None

        parts = order_by.strip().split()

        field = parts[0]

        if field not in valid_fields:

            raise ValueError(
                f"Invalid order_by field '{field}' "
                f"for DocType '{doctype}'. "
                f"Available fields: {sorted(valid_fields)}"
            )

        direction = ""

        if len(parts) > 1:

            direction = parts[1].lower()

            if direction not in ("asc", "desc"):

                raise ValueError(
                    f"Invalid order direction '{direction}'. "
                    f"Use 'asc' or 'desc'."
                )

        return f"{field} {direction}".strip()

    def get_system_prompt(self, provider_doc=None):
        doctypes = self._get_doctype_list_str(provider_doc)
        prompt = getattr(provider_doc, "system_prompt", "") if provider_doc else ""
        today_date = today()
        
        prompt = prompt.replace('{doctype_list_str}', doctypes)
        prompt = prompt.replace('{today_date}', today_date)
        
        return prompt

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
        if provider_doc and provider_doc.allowed_doctypes:
            return ", ".join(d.document_type for d in provider_doc.allowed_doctypes)
        return "None (You currently do not have access to any DocTypes. If the user asks for data, tell them they must configure the Allowed DocTypes table first.)"
