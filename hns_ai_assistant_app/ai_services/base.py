import frappe
import json
from hns_ai_assistant_app.utils import ERPNextTools


class BaseAIService:
    def __init__(self, provider_doc):
        self.provider_doc = provider_doc
        self.model = provider_doc.model
        self.base_url = provider_doc.base_url
        self.api_key = (provider_doc.get_password("api_key") or "").strip()

    def _to_json_str(self, val):
        if not val:
            return ""
        if type(val) in (dict, list):
            try:
                return json.dumps(val, indent=4)
            except Exception:
                return str(val)
        return str(val)

    def format_captured_data(self, captured_items):
        if not captured_items:
            return ""

        doctypes_with_records = set()
        for item in captured_items:
            records = item.get("data")
            if type(records) is list and records and type(records[0]) is dict:
                if not (len(records) == 1 and len(records[0]) == 1 and ("count" in records[0] or "sum" in records[0])):
                    doctypes_with_records.add(item.get("doctype"))

        sections = []
        for item in captured_items:
            doctype = item.get("doctype", "Data")
            records = item.get("data")
            error = item.get("error")
            if error:
                sections.append(
                    f"<div class='aak-table-container' style='margin: 8px 0; background: #ffffff; border: 1px solid #fee2e2; border-radius: 10px; padding: 12px 14px; color: #dc2626; font-size: 12.5px;'>"
                    f"<strong>Error querying {doctype}:</strong> {error}"
                    f"</div>"
                )
                continue
            if not records:
                sections.append(
                    f"<div class='aak-table-container' style='margin: 8px 0; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 14px; color: #64748b; font-size: 12.5px;'>"
                    f"No records found for <strong>{doctype}</strong>."
                    f"</div>"
                )
                continue

            if type(records) is list and len(records) == 1 and type(records[0]) is dict and len(records[0]) == 1 and ("count" in records[0] or "sum" in records[0]):
                if doctype in doctypes_with_records:
                    continue
                op_key = "count" if "count" in records[0] else "sum"
                op_val = records[0][op_key]
                sections.append(
                    f"<div class='aak-table-container' style='margin: 8px 0; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 16px;'>"
                    f"<div style='display: flex; align-items: center; justify-content: space-between;'>"
                    f"<span style='font-size: 13px; font-weight: 600; color: #1e293b;'>{doctype} ({op_key.title()})</span>"
                    f"<span style='font-size: 12px; font-weight: 700; color: #0284c7; background: #e0f2fe; padding: 2px 10px; border-radius: 12px;'>{op_val}</span>"
                    f"</div>"
                    f"</div>"
                )
                continue

            if type(records) is list and records and type(records[0]) is dict:
                headers = list(records[0].keys())
                num_th = "<th style='padding: 9px 14px; font-weight: 600; font-size: 11.5px; color: #475569; text-transform: uppercase; letter-spacing: 0.4px; border-bottom: 2px solid #cbd5e1; background: #f8fafc; white-space: nowrap !important; word-break: normal !important; position: sticky; top: 0; width: 40px;'>#</th>"
                header_html = num_th + "".join(
                    f"<th style='padding: 9px 14px; font-weight: 600; font-size: 11.5px; color: #475569; text-transform: uppercase; letter-spacing: 0.4px; border-bottom: 2px solid #cbd5e1; background: #f8fafc; white-space: nowrap !important; word-break: normal !important; position: sticky; top: 0;'>{h.replace('_', ' ').title()}</th>"
                    for h in headers
                )
                rows_html = []
                for idx, r in enumerate(records, 1):
                    num_td = f"<td style='padding: 9px 14px; color: #64748b; font-weight: 600; border-bottom: 1px solid #f1f5f9; white-space: nowrap !important; word-break: normal !important;'>{idx}</td>"
                    cells = num_td + "".join(
                        f"<td style='padding: 9px 14px; color: #1e293b; border-bottom: 1px solid #f1f5f9; white-space: nowrap !important; word-break: normal !important;'>{str(r.get(h, '')) if r.get(h) is not None else ''}</td>"
                        for h in headers
                    )
                    rows_html.append(f"<tr>{cells}</tr>")

                table_html = (
                    f"<div class='aak-table-container' style='margin: 8px 0; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); overflow: hidden; width: 100%; max-width: 100%; min-width: 0;'>"
                    f"<div class='aak-table-header' style='display: flex; align-items: center; justify-content: space-between; padding: 9px 14px; background: #f8fafc; border-bottom: 1px solid #e2e8f0;'>"
                    f"<span class='aak-table-title' style='font-size: 13px; font-weight: 600; color: #1e293b;'>{doctype}</span>"
                    f"<span class='aak-table-badge' style='font-size: 11px; font-weight: 600; color: #475569; background: #e2e8f0; padding: 2px 8px; border-radius: 12px;'>{len(records)} record{'s' if len(records) > 1 else ''}</span>"
                    f"</div>"
                    f"<div class='aak-table-scroll' style='width: 100%; max-width: 100%; overflow-x: auto; overflow-y: hidden; -webkit-overflow-scrolling: touch; display: block;'>"
                    f"<table class='aak-data-table' style='width: max-content; min-width: 100%; border-collapse: collapse; font-size: 12px; line-height: 1.5; text-align: left; table-layout: auto; margin: 0;'>"
                    f"<thead><tr>{header_html}</tr></thead>"
                    f"<tbody>{''.join(rows_html)}</tbody>"
                    f"</table>"
                    f"</div>"
                    f"</div>"
                )
                sections.append(table_html)
            elif type(records) is dict:
                sections.append(f"<pre class='aak-json-block'><code>{json.dumps(records, indent=4)}</code></pre>")
            else:
                sections.append(f"<p>{str(records)}</p>")
        return "\n\n".join(sections)

    def log_interaction(self, user_query, ai_response, response_data=None, api_response=None, usage_details=None, prompt=None, erpnext_context=None):
        try:
            doc = frappe.get_doc({
                "doctype": "Hns Akansha Log",
                "user": frappe.session.user,
                "user_query": user_query,
                "ai_response": self._to_json_str(ai_response) if type(ai_response) in (dict, list) else (ai_response or ""),
                "erpnext_context": 1 if frappe.utils.cint(erpnext_context) else 0,
                "ai_api_response": self._to_json_str(api_response),
                "prompt": self._to_json_str(prompt),
                "response_data": self._to_json_str(response_data),
                "usage_details": self._to_json_str(usage_details)
            })
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(title="Hns Akansha Log Error", message=str(e))

    def log_error(self, user_query, error_message, prompt=None, erpnext_context=None):
        self.log_interaction(
            user_query=user_query,
            ai_response=error_message,
            prompt=prompt,
            erpnext_context=erpnext_context
        )

    def _prepare_tools_and_context(self, enable_context, system_prompt=None):
        tools_manager = ERPNextTools()
        tools_manager.set_provider(self.provider_doc)
        
        tool_schema = None
        
        if tools_manager.is_erpnext_context_enabled(enable_context):
            if not system_prompt or system_prompt == "You are a helpful assistant.":
                system_prompt = tools_manager.get_system_prompt(self.provider_doc)
            tool_schema = tools_manager.get_query_tool_schema()
        else:
            if not system_prompt:
                system_prompt = "You are a helpful assistant."
                
        return tools_manager, system_prompt, tool_schema

    def _execute_tool(self, function_name, args, tools_manager, messages_for_logging=None, enable_context=None, user_query=None):
        if function_name == "query_erpnext_data":
            tool_result = tools_manager.query_erpnext_data(
                doctype=args.get('doctype', ''),
                fields=args.get('fields', []),
                filters=args.get('filters', '{}'),
                operation=args.get('operation', 'list'),
                order_by=args.get('order_by'),
                limit=args.get('limit'),
                offset=args.get('offset', 0),
                sum_field=args.get('sum_field'),
                group_by=args.get('group_by'),
            )
            
            if type(tool_result) is dict and "error" in tool_result:
                error_msg = tool_result["error"]
                log_data = (
                    tools_manager.captured_data if len(tools_manager.captured_data) > 1
                    else (tools_manager.captured_data[0] if tools_manager.captured_data else None)
                )
                prompt_log = json.dumps(messages_for_logging, indent=4) if messages_for_logging else None
                error_api_log = {
                    "functionCall": {
                        "name": function_name,
                        "args": args
                    }
                }
                self.log_interaction(
                    user_query=user_query or "",
                    ai_response=error_msg,
                    response_data=log_data,
                    api_response=json.dumps(error_api_log, indent=4),
                    usage_details=None,
                    prompt=prompt_log,
                    erpnext_context=enable_context
                )
                return {"error": error_msg}
                
            return tool_result
        else:
            return {"error": f"Unknown function {function_name}"}

    def generate_response(self, message, enable_context=None, system_prompt=None):
        raise NotImplementedError("This method must be implemented by subclasses.")



