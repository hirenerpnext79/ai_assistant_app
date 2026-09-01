import requests
import frappe
import json
from ai_assistant_app.ai_services.base import BaseAIService

class OpenRouterService(BaseAIService):
    def validate_configuration(self):
        if not self.model:
            frappe.throw(frappe._("Model is required for OpenRouter Provider Configuration."))
            
        if not self.base_url:
            frappe.throw(frappe._("Base URL is required for OpenRouter Provider Configuration."))

    def generate_response(self, user_message, enable_context=None, system_prompt=None):
        self.validate_configuration()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        from ai_assistant_app.utils import ERPNextTools
        tools_manager = ERPNextTools()
        tools_manager.set_provider(self.provider_doc)

        tools = []
        if tools_manager.is_erpnext_context_enabled(enable_context):
            if not system_prompt or system_prompt == "You are a helpful assistant.":
                system_prompt = tools_manager.get_system_prompt(self.provider_doc)
            
            tool_schema = tools_manager.get_query_tool_schema()
            tools = [{
                "type": "function",
                "function": tool_schema
            }]
        else:
            if not system_prompt:
                system_prompt = "You are a helpful assistant."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        max_turns = 3
        current_turn = 0
        final_content = ""
        total_usage = {}
        
        while current_turn < max_turns:
            current_turn += 1
            
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.provider_doc.get("max_tokens") or 2048
            }
            if tools:
                payload["tools"] = tools
            
            response = requests.post(self.base_url, headers=headers, json=payload)
            self.handle_api_errors(response)
            
            result_data = response.json()
            if 'choices' not in result_data or not result_data['choices']:
                frappe.throw(f"Unexpected response format: {result_data}")
                
            choice = result_data['choices'][0]
            message_obj = choice.get('message', {})
            
            usage = result_data.get('usage', {})
            total_usage['total_tokens'] = total_usage.get('total_tokens', 0) + usage.get('total_tokens', 0)
            total_usage['prompt_tokens'] = total_usage.get('prompt_tokens', 0) + usage.get('prompt_tokens', 0)
            total_usage['completion_tokens'] = total_usage.get('completion_tokens', 0) + usage.get('completion_tokens', 0)

            if message_obj.get('tool_calls'):
                messages.append(message_obj)
                
                for tool_call in message_obj['tool_calls']:
                    function_name = tool_call['function']['name']
                    try:
                        args = json.loads(tool_call['function']['arguments'])
                    except Exception:
                        args = {}
                        
                    if function_name == "query_erpnext_data":
                        tool_result = tools_manager.query_erpnext_data(
                            doctype=args.get('doctype', ''),
                            fields=args.get('fields', []),
                            filters=args.get('filters', '{}')
                        )
                    else:
                        tool_result = {"error": f"Unknown function {function_name}"}
                        
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call['id'],
                        "content": json.dumps(tool_result)
                    })
            else:
                final_content = message_obj.get('content', '')
                break

        usage_token = total_usage.get('total_tokens', 0)
        usage_details = json.dumps(total_usage)
        log_data = tools_manager.captured_data[0] if tools_manager.captured_data else None
        
        self.log_interaction(user_message, final_content, log_data, None, usage_token, usage_details)
        
        return final_content

    def handle_api_errors(self, response):
        if response.status_code == 200:
            return
            
        try:
            error_data = response.json()
            error_message = error_data.get('error', {}).get('message', response.text)
        except Exception:
            error_message = response.text
            
        frappe.throw(frappe._(f"OpenRouter API Error: {error_message} (Status Code: {response.status_code})"))
