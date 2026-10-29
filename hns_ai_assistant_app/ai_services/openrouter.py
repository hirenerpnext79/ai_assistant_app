import requests
import frappe
import json
from hns_ai_assistant_app.ai_services.base import BaseAIService

class OpenRouterService(BaseAIService):
    def validate_configuration(self):
        if not self.model:
            frappe.throw(frappe._("Model is required for OpenRouter Provider Configuration."))
            
        if not self.base_url:
            frappe.throw(frappe._("Base URL is required for OpenRouter Provider Configuration."))

    def generate_response(self, user_message, enable_context=None, system_prompt=None):
        prompt_log = None
        try:
            self.validate_configuration()
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        
            tools_manager, final_system_prompt, tool_schema = self._prepare_tools_and_context(enable_context, system_prompt)

            tools = []
            if tool_schema:
                tools = [{
                    "type": "function",
                    "function": tool_schema
                }]

            messages = [
                {"role": "system", "content": final_system_prompt},
                {"role": "user", "content": user_message}
            ]

            max_turns = 3
            current_turn = 0
            final_content = ""
            total_usage = {}
            logged_function_calls = []
            logged_function_responses = []
        
            while current_turn < max_turns:
                current_turn += 1
            
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.1
                }
                if tools:
                    payload["tools"] = tools
                    payload["parallel_tool_calls"] = False
            
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
                            
                        tool_result = self._execute_tool(
                            function_name=function_name,
                            args=args,
                            tools_manager=tools_manager,
                            messages_for_logging=messages,
                            enable_context=enable_context,
                            user_query=user_message
                        )
                        
                        if type(tool_result) is dict and "error" in tool_result:
                            return tool_result["error"]
                        
                        logged_function_calls.append({
                            "name": function_name,
                            "args": args
                        })
                        logged_function_responses.append({
                            "name": function_name,
                            "response": tool_result if type(tool_result) is dict else {"result": tool_result}
                        })
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call['id'],
                            "content": json.dumps(tool_result)
                        })
                else:
                    final_content = message_obj.get('content', '')
                    break
                    
            log_data = (
                tools_manager.captured_data if len(tools_manager.captured_data) > 1
                else (tools_manager.captured_data[0] if tools_manager.captured_data else None)
            )
            prompt_log = json.dumps(messages, indent=4)
            usage_details = json.dumps(total_usage, indent=4)

            if not final_content and tools_manager.captured_data:
                final_content = self.format_captured_data(tools_manager.captured_data)

            api_log = {}
            if logged_function_calls:
                api_log = {
                    "functionCall": logged_function_calls if len(logged_function_calls) > 1 else logged_function_calls[0]
                }
            
            self.log_interaction(
                user_query=user_message,
                ai_response=final_content,
                response_data=log_data,
                api_response=json.dumps(api_log, indent=4) if api_log else "",
                usage_details=usage_details,
                prompt=prompt_log,
                erpnext_context=enable_context
            )
        
            return final_content

        except Exception as e:
            error_msg = f"OpenRouter API Error: {str(e)}"
            self.log_error(user_message, error_msg, prompt=prompt_log, erpnext_context=enable_context)
            frappe.log_error(title="OpenRouter API Error", message=error_msg)
            raise Exception(error_msg)

    def handle_api_errors(self, response):
        if response.status_code == 200:
            return
            
        if response.status_code == 429:
            raise Exception("Rate limit reached. Please wait and try again.")
            
        try:
            error_data = response.json()
            error_message = error_data.get('error', {}).get('message', response.text)
        except Exception:
            error_message = response.text
            
        frappe.throw(frappe._(f"OpenRouter API Error: {error_message} (Status Code: {response.status_code})"))