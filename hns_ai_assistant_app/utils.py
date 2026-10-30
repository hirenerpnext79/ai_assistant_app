import json
import re
import frappe
from frappe.utils import today

SETTINGS_DOCTYPE = "Hns AI Assistant App Setting"
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
AGGREGATE_FIELD_PATTERN = re.compile(
    r"^(sum|count|avg|min|max)\s*\(\s*`?([a-zA-Z0-9_*]+)`?\s*\)(?:\s+as\s+`?([a-zA-Z0-9_]+)`?)?$",
    re.IGNORECASE
)


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
        sum_field: str = None,
        group_by: str = None
    ) -> dict:
        try:
            self._check_doctype_access(doctype)
            valid_fields = self._get_valid_fields(doctype)
            safe_fields, allowed_aliases = self._validate_and_sanitize_fields(fields, valid_fields, doctype)
            self._validate_sum_operation(operation, sum_field, valid_fields, doctype)

            parsed_filters = self._prepare_filters(filters, valid_fields, doctype)
            safe_group_by = self._validate_group_by(group_by, valid_fields, doctype)
            safe_order_by = self._prepare_order_by(order_by, valid_fields, doctype, allowed_aliases, operation, parsed_filters)

            meta = frappe.get_meta(doctype)
            if meta.issingle:
                data = self._query_single_doctype(doctype, safe_fields)
            elif operation == "count":
                data = self._query_count(doctype, parsed_filters)
            elif operation == "sum":
                data = self._query_sum(doctype, parsed_filters, sum_field)
            else:
                data = self._query_list(doctype, safe_fields, parsed_filters, safe_order_by, safe_group_by, limit, offset)

            data = json.loads(frappe.as_json(data))
            final_sql_query = (frappe.db.last_query or "").strip()

            captured_entry = {
                "doctype": doctype,
                "operation": operation,
                "final_sql_query": final_sql_query,
                "data": data
            }
            if safe_group_by:
                captured_entry["group_by"] = safe_group_by

            self.captured_data.append(captured_entry)
            return {"data": data}

        except Exception as e:
            error_msg = str(e)
            final_sql_query = (frappe.db.last_query or "").strip()
            self.captured_data.append({
                "doctype": doctype,
                "error": error_msg,
                "final_sql_query": final_sql_query
            })
            return {"error": error_msg}

    def _get_valid_fields(self, doctype: str) -> set:
        meta = frappe.get_meta(doctype)
        valid_fields = {df.fieldname for df in meta.fields if df.fieldname}
        valid_fields.update({
            "name",
            "owner",
            "creation",
            "modified",
            "modified_by",
            "docstatus",
            "idx"
        })
        return valid_fields

    def _validate_sum_operation(self, operation: str, sum_field: str, valid_fields: set, doctype: str):
        if operation != "sum":
            return
        if not sum_field:
            raise ValueError("sum_field is required when operation='sum'.")
        if sum_field not in valid_fields:
            raise ValueError(
                f"Invalid sum field '{sum_field}' for DocType '{doctype}'. "
                f"Available fields: {sorted(valid_fields)}"
            )

    def _prepare_filters(self, filters, valid_fields: set, doctype: str):
        parsed = self._parse_filters(filters)
        self._validate_filter_fields(parsed, valid_fields, doctype)
        return self._normalize_datetime_filters(parsed, doctype)

    def _prepare_order_by(self, order_by, valid_fields, doctype, allowed_aliases, operation, parsed_filters):
        safe_order_by = self._validate_order_by(order_by, valid_fields, doctype, allowed_aliases)
        if not safe_order_by and operation == "list" and self._has_creation_filter(parsed_filters):
            return "creation desc"
        return safe_order_by

    def _query_count(self, doctype: str, filters) -> list:
        count = frappe.db.count(doctype, filters=filters)
        return [{"count": count}]

    def _query_list(self, doctype, safe_fields, parsed_filters, safe_order_by, safe_group_by, limit, offset):
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
        if safe_group_by:
            query_args["group_by"] = safe_group_by

        return frappe.get_all(**query_args)

    def _validate_filter_fields(self, filters, valid_fields, doctype):
        if not filters:
            return

        if type(filters) is dict:
            for field in filters.keys():
                if field not in valid_fields:
                    raise ValueError(
                        f"Invalid filter field '{field}' for DocType '{doctype}'. "
                        f"Available fields: {sorted(valid_fields)}"
                    )
            return

        if type(filters) is list:
            for condition in filters:
                if type(condition) not in (list, tuple) or not condition:
                    continue
                field = condition[0]
                if field not in valid_fields:
                    raise ValueError(
                        f"Invalid filter field '{field}' for DocType '{doctype}'. "
                        f"Available fields: {sorted(valid_fields)}"
                    )

    def _validate_and_sanitize_fields(self, fields, valid_fields, doctype):
        if not fields:
            raise ValueError(f"No fields specified for DocType '{doctype}'.")

        if fields == ["*"]:
            return ["*"], set()

        safe_fields = []
        allowed_aliases = set()

        for field in fields:
            field_str = str(field).strip()
            if not field_str:
                continue

            agg_match = AGGREGATE_FIELD_PATTERN.match(field_str)
            if agg_match:
                func_name = agg_match.group(1).lower()
                inner_field = agg_match.group(2).strip("`")
                alias = (agg_match.group(3) or "").strip("`")

                if inner_field != "*" and inner_field not in valid_fields:
                    raise ValueError(
                        f"Invalid field '{inner_field}' in aggregate '{field_str}' for DocType '{doctype}'. "
                        f"Available fields: {sorted(valid_fields)}"
                    )

                if alias:
                    allowed_aliases.add(alias)
                    safe_fields.append(f"{func_name}({inner_field}) as {alias}")
                else:
                    safe_fields.append(f"{func_name}({inner_field})")
                continue

            clean_field = field_str.strip("` \t\r\n").split(".")[-1].strip("`")
            if clean_field not in valid_fields:
                raise ValueError(
                    f"Invalid field '{clean_field}' for DocType '{doctype}'. "
                    f"Available fields: {sorted(valid_fields)}"
                )
            safe_fields.append(clean_field)

        if not safe_fields:
            raise ValueError(f"No valid fields specified for DocType '{doctype}'.")

        return safe_fields, allowed_aliases

    def _validate_group_by(self, group_by, valid_fields, doctype):
        if not group_by:
            return None

        cleaned_fields = []
        raw_clauses = [c.strip() for c in str(group_by).split(",") if c.strip()]

        for item in raw_clauses:
            field = item.strip("` \t\r\n").split(".")[-1].strip("`")
            if not field or field not in valid_fields:
                raise ValueError(
                    f"Invalid group_by field '{field or item}' for DocType '{doctype}'. "
                    f"Available fields: {sorted(valid_fields)}"
                )
            cleaned_fields.append(field)

        return ", ".join(cleaned_fields) if cleaned_fields else None

    def _validate_order_by(self, order_by, valid_fields, doctype, allowed_aliases=None):
        if not order_by:
            return None

        combined_valid = set(valid_fields)
        if allowed_aliases:
            combined_valid.update(allowed_aliases)

        cleaned_clauses = []
        raw_clauses = [c.strip() for c in str(order_by).split(",") if c.strip()]

        for clause in raw_clauses:
            tokens = clause.strip().split()
            if not tokens:
                continue

            direction = self._parse_order_direction(tokens)
            field_expr = " ".join(tokens[:-1]) if len(tokens) > 1 and direction else tokens[0]
            stripped_expr = field_expr.strip("` \t\r\n")

            agg_match = AGGREGATE_FIELD_PATTERN.match(stripped_expr)
            if agg_match:
                func_name = agg_match.group(1).lower()
                inner_field = agg_match.group(2).strip("`")
                if inner_field != "*" and inner_field not in valid_fields:
                    raise ValueError(
                        f"Invalid order_by field '{field_expr}' for DocType '{doctype}'. "
                        f"Available fields: {sorted(valid_fields)}"
                    )
                cleaned_clauses.append(f"{func_name}({inner_field}) {direction}".strip())
                continue

            field = stripped_expr.split(".")[-1].strip("`")
            if not field or field not in combined_valid:
                raise ValueError(
                    f"Invalid order_by field '{field or field_expr}' for DocType '{doctype}'. "
                    f"Available fields: {sorted(combined_valid)}"
                )

            cleaned_clauses.append(f"{field} {direction}".strip())

        return ", ".join(cleaned_clauses) if cleaned_clauses else None

    def _parse_order_direction(self, tokens: list) -> str:
        last_token = tokens[-1].strip("` \t\r\n,;.").lower()
        if last_token in ("desc", "descending", "decending"):
            return "desc"
        if last_token in ("asc", "ascending"):
            return "asc"
        if len(tokens) > 1:
            raise ValueError(f"Invalid order direction '{tokens[-1]}'. Use 'asc' or 'desc'.")
        return ""

    def get_system_prompt(self, provider_doc=None):
        try:
            from hns_ai_assistant_app.hns_ai_assistant_app.doctype.hns_ai_assistant_rule.hns_ai_assistant_rule import (
                get_active_rules,
            )
            from frappe.utils import now_datetime
            doctypes = self._get_doctype_list_str(provider_doc)
            today_date = f"{today()} ({now_datetime().strftime('%A')})"
            return get_active_rules(doctypes=doctypes, today_date=today_date)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Hns AI Assistant: get_system_prompt error")
            return "You are a helpful assistant."

    def _check_doctype_access(self, doctype: str):
        if not self.provider_doc:
            return
        from hns_ai_assistant_app.api.ai_handler import check_doctype_permission
        is_allowed, msg = check_doctype_permission(self.provider_doc, doctype)
        if not is_allowed:
            frappe.throw(msg)

    def _parse_filters(self, filters):
        if type(filters) in (dict, list):
            return filters
        if type(filters) is str and filters:
            try:
                return frappe.parse_json(filters)
            except Exception:
                pass
        return {}

    def _normalize_datetime_filters(self, parsed_filters, doctype):
        try:
            meta = frappe.get_meta(doctype)
            datetime_fields = {
                df.fieldname for df in meta.fields
                if df.fieldname and df.fieldtype in ("Datetime", "Time")
            }
            datetime_fields.update({"creation", "modified"})

            if type(parsed_filters) is dict:
                return self._normalize_dict_datetime_filters(parsed_filters, datetime_fields)

            if type(parsed_filters) is list:
                return self._normalize_list_datetime_filters(parsed_filters, datetime_fields)

        except Exception:
            frappe.log_error(frappe.get_traceback(), "Hns AI Assistant: _normalize_datetime_filters error")

        return parsed_filters

    def _normalize_dict_datetime_filters(self, filters: dict, datetime_fields: set) -> dict:
        normalized = {}
        for field, val in filters.items():
            if field in datetime_fields:
                if type(val) is str and DATE_PATTERN.match(val):
                    val = ["between", [f"{val} 00:00:00", f"{val} 23:59:59.999999"]]
                elif type(val) in (list, tuple) and len(val) == 2:
                    op, c_val = self._convert_datetime_val(val[0], val[1])
                    val = [op, c_val]
            normalized[field] = val
        return normalized

    def _normalize_list_datetime_filters(self, filters: list, datetime_fields: set) -> list:
        normalized = []
        for item in filters:
            if type(item) in (list, tuple) and len(item) == 3 and item[0] in datetime_fields:
                op, c_val = self._convert_datetime_val(item[1], item[2])
                normalized.append([item[0], op, c_val])
            elif type(item) in (list, tuple) and len(item) == 4 and item[1] in datetime_fields:
                op, c_val = self._convert_datetime_val(item[2], item[3])
                normalized.append([item[0], item[1], op, c_val])
            else:
                normalized.append(item)
        return normalized

    def _convert_datetime_val(self, op, val):
        if type(val) is str and DATE_PATTERN.match(val):
            if op in ("=", "=="):
                return "between", [f"{val} 00:00:00", f"{val} 23:59:59.999999"]
            if op in ("<=", ">"):
                return op, f"{val} 23:59:59.999999"
            if op in (">=", "<"):
                return op, f"{val} 00:00:00"
        if str(op).lower() == "between" and type(val) in (list, tuple) and len(val) == 2:
            start = f"{val[0]} 00:00:00" if type(val[0]) is str and DATE_PATTERN.match(val[0]) else val[0]
            end = f"{val[1]} 23:59:59.999999" if type(val[1]) is str and DATE_PATTERN.match(val[1]) else val[1]
            return "between", [start, end]
        return op, val

    def _has_creation_filter(self, parsed_filters):
        if type(parsed_filters) is dict:
            return "creation" in parsed_filters
        if type(parsed_filters) is list:
            for condition in parsed_filters:
                if type(condition) in (list, tuple) and condition and condition[0] == "creation":
                    return True
        return False

    def _query_single_doctype(self, doctype: str, fields: list) -> list:
        doc = frappe.get_single(doctype).as_dict()
        if fields and fields != ["*"]:
            return [{f: doc.get(f) for f in fields}]
        return [doc]

    def _query_sum(self, doctype: str, filters, sum_field: str) -> list:
        result = frappe.get_all(
            doctype,
            filters=filters,
            fields=[f"sum(`{sum_field}`) as total"]
        )
        total = 0
        if result and result[0].get("total") is not None:
            total = result[0].get("total")
        return [{"sum": total}]

    def _get_doctype_list_str(self, provider_doc) -> str:
        try:
            if not provider_doc:
                return "All ERPNext DocTypes"
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
