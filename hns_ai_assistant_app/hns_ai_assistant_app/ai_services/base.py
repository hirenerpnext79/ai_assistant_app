import frappe
import json
from hns_ai_assistant_app.utils import ERPNextTools


class BaseAIService:
    def __init__(self, provider_doc):
        self.provider_doc = provider_doc
        self.model = provider_doc.model
        self.base_url = provider_doc.base_url
        self.api_key = (provider_doc.get_password("api_key") or "").strip()
        try:
            self.max_tokens = provider_doc.max_tokens
        except Exception:
            self.max_tokens = 1000

    def log_interaction(self, user_query, ai_response, response_data=None, api_response=None, usage_details=None, prompt=None, erpnext_context=None):
        try:
            doc = frappe.get_doc({
                "doctype": "Hns Akansha Log",
                "user": frappe.session.user,
                "user_query": user_query,
                "ai_response": ai_response,
                "erpnext_context": 1 if frappe.utils.cint(erpnext_context) else 0,
                "response_data": json.dumps(response_data) if response_data else None,
                "ai_api_response": api_response,
                "usage_details": usage_details,
                "prompt": prompt
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
        """Execute a tool and return the result dictionary or log an error if it fails."""
        if function_name == "query_erpnext_data":
            tool_result = tools_manager.query_erpnext_data(
                doctype=args.get('doctype', ''),
                fields=args.get('fields', []),
                filters=args.get('filters', '{}'),
                operation=args.get('operation', 'list'),
                order_by=args.get('order_by'),
                limit=args.get('limit'),
                sum_field=args.get('sum_field'),
            )
            
            if isinstance(tool_result, dict) and "error" in tool_result:
                error_msg = tool_result["error"]
                log_data = tools_manager.captured_data[0] if tools_manager.captured_data else None
                prompt_log = json.dumps(messages_for_logging, indent=2) if messages_for_logging else None
                
                self.log_interaction(
                    user_query=user_query or "",
                    ai_response=error_msg,
                    response_data=log_data,
                    api_response=json.dumps(tool_result),
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



