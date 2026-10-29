import frappe
import json
import requests
from hns_ai_assistant_app.ai_services.base import BaseAIService


def _strip_gemini_unsupported(schema):
    unsupported = {"additionalProperties", "minItems", "maxItems", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"}
    if type(schema) is dict:
        return {k: _strip_gemini_unsupported(v) for k, v in schema.items() if k not in unsupported}
    if type(schema) is list:
        return [_strip_gemini_unsupported(i) for i in schema]
    return schema


class GeminiService(BaseAIService):
    def get_api_url(self, action="generateContent"):
        base_url = self.base_url or "https://generativelanguage.googleapis.com/v1beta"
        base_url = base_url.rstrip("/")
        return f"{base_url}/models/{self.model}:{action}?key={self.api_key}"

    def _execute_api_call(self, payload):
        url = self.get_api_url()
        headers = {"Content-Type": "application/json"}

        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 429:
            raise Exception("Rate limit reached. Please wait and try again.")
        response.raise_for_status()

        return response.json()

    def generate(self, text, prompt):
        system_instruction = "You are a helpful assistant. Always return JSON. The JSON should contain title, summary, hashtags (array of strings), and keywords (array of strings)."
        payload = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"role": "user", "parts": [{"text": f"{prompt}\n\nDocument Text:\n{text}"}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        }
        try:
            data = self._execute_api_call(payload)
            response_text = data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            response_text = ""

        return response_text, {}

    def generate_response(self, message, enable_context=None, system_prompt=None):
        tools_manager, final_system_prompt, tool_schema = self._prepare_tools_and_context(enable_context, system_prompt)
        
        tools = []
        if tool_schema:
            tools = [{
                "functionDeclarations": [{
                    "name": tool_schema["name"],
                    "description": tool_schema["description"],
                    "parameters": _strip_gemini_unsupported(tool_schema["parameters"])
                }]
            }]

        contents = [{"role": "user", "parts": [{"text": message}]}]
        payload = {
            "systemInstruction": {"parts": [{"text": final_system_prompt}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.1}
        }
        
        if tools:
            payload["tools"] = tools

        max_turns = 4
        current_turn = 0
        all_function_calls = []
        response_text = ""

        try:
            while current_turn < max_turns:
                current_turn += 1
                data = self._execute_api_call(payload)
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                function_calls = [p["functionCall"] for p in parts if "functionCall" in p]

                if function_calls:
                    all_function_calls.extend(function_calls)
                    contents.append({"role": "model", "parts": parts})
                    function_responses = []
                    
                    for func_call in function_calls:
                        if self._should_skip_redundant_call(func_call, function_calls):
                            function_responses.append({
                                "functionResponse": {
                                    "name": func_call["name"],
                                    "response": {"result": "Skipped redundant probe query without filters"}
                                }
                            })
                            continue

                        result = self._execute_tool(
                            function_name=func_call["name"],
                            args=func_call.get("args", {}),
                            tools_manager=tools_manager,
                            messages_for_logging=payload,
                            enable_context=enable_context,
                            user_query=message
                        )
                        
                        if type(result) is dict and "error" in result:
                            return result["error"]
                            
                        function_responses.append({
                            "functionResponse": {
                                "name": func_call["name"],
                                "response": result if type(result) is dict else {"result": result}
                            }
                        })
                        
                    contents.append({"role": "user", "parts": function_responses})
                else:
                    response_text = "".join([p["text"] for p in parts if "text" in p])
                    break

            if not response_text and tools_manager.captured_data:
                response_text = self.format_captured_data(tools_manager.captured_data)
            
            usage_metadata = data.get("usageMetadata", {})
            usage_details = {
                "prompt_token_count": usage_metadata.get("promptTokenCount", 0),
                "candidates_token_count": usage_metadata.get("candidatesTokenCount", 0),
                "total_token_count": usage_metadata.get("totalTokenCount", 0)
            } if usage_metadata else {}

            log_data = (
                tools_manager.captured_data if len(tools_manager.captured_data) > 1
                else (tools_manager.captured_data[0] if tools_manager.captured_data else None)
            )
            prompt_log = json.dumps(payload, indent=4)

            api_log = {}
            if all_function_calls:
                api_log = {
                    "functionCall": all_function_calls if len(all_function_calls) > 1 else all_function_calls[0]
                }
            
            self.log_interaction(
                user_query=message,
                ai_response=response_text,
                response_data=log_data,
                api_response=json.dumps(api_log, indent=4) if api_log else "",
                usage_details=json.dumps(usage_details, indent=4) if usage_details else None,
                prompt=prompt_log,
                erpnext_context=enable_context
            )
            return response_text

        except Exception as e:
            error_msg = f"Error from Google Gemini API: {str(e)}"
            prompt_log = json.dumps(payload, indent=2) if "payload" in dir() else None
            self.log_error(message, error_msg, prompt=prompt_log, erpnext_context=enable_context)
            frappe.log_error(title="Gemini API Error", message=error_msg)
            raise Exception(error_msg)

    def _should_skip_redundant_call(self, func_call, function_calls):
        if len(function_calls) <= 1:
            return False
        args = func_call.get("args", {})
        filters = args.get("filters")
        doctype = args.get("doctype")
        if (not filters or filters == {}) and doctype:
            return any(
                f != func_call and f.get("args", {}).get("doctype") == doctype and f.get("args", {}).get("filters")
                for f in function_calls
            )
        return False