import frappe
import json
import requests
from ai_assistant_app.ai_services.base import BaseAIService

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
        if self.max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = int(self.max_tokens)
        
        try:
            data = self._execute_api_call(payload)
            response_text = data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            response_text = ""
            
        return response_text, {}

    def _execute_tools(self, function_calls, tools_manager):
        function_responses = []
        for func_call in function_calls:
            if func_call["name"] == "query_erpnext_data":
                args = func_call.get("args", {})
                tool_result = tools_manager.query_erpnext_data(
                    doctype=args.get("doctype"),
                    fields=args.get("fields"),
                    filters=args.get("filters"),
                    limit=args.get("limit", 50)
                )
                function_responses.append({
                    "functionResponse": {
                        "name": func_call["name"],
                        "response": tool_result if isinstance(tool_result, dict) else {"result": tool_result}
                    }
                })
        return function_responses

    def generate_response(self, message, enable_context=None):
        from ai_assistant_app.utils import ERPNextTools
        tools_manager = ERPNextTools()
        tools_manager.set_provider(self.provider_doc)

        tools = []
        if tools_manager.is_erpnext_context_enabled(enable_context):
            system_instruction = tools_manager.get_system_prompt(self.provider_doc)
            schema_dict = tools_manager.get_query_tool_schema()
            tools = [{
                "functionDeclarations": [{
                    "name": schema_dict["name"], 
                    "description": schema_dict["description"], 
                    "parameters": schema_dict["parameters"]
                }]
            }]
        else:
            system_instruction = "You are a helpful assistant."

        contents = [{"role": "user", "parts": [{"text": message}]}]
        payload = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.7}
        }
        if self.max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = int(self.max_tokens)
        
        if tools:
            payload["tools"] = tools

        try:
            data = self._execute_api_call(payload)
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            function_calls = [p["functionCall"] for p in parts if "functionCall" in p]
            
            if function_calls:
                contents.append({"role": "model", "parts": parts})
                function_responses = self._execute_tools(function_calls, tools_manager)
                contents.append({"role": "user", "parts": function_responses})
                
                data = self._execute_api_call(payload)
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])

            response_text = "".join([p["text"] for p in parts if "text" in p])
            usage_metadata = data.get("usageMetadata", {})
            usage_details = {
                "prompt_token_count": usage_metadata.get("promptTokenCount", 0),
                "candidates_token_count": usage_metadata.get("candidatesTokenCount", 0),
                "total_token_count": usage_metadata.get("totalTokenCount", 0)
            } if usage_metadata else {}
            
            log_data = tools_manager.captured_data[0] if tools_manager.captured_data else None
            prompt_log = json.dumps(payload, indent=2)
            self.log_interaction(
                user_query=message, 
                ai_response=response_text, 
                response_data=log_data, 
                api_response=json.dumps(data),
                usage_token=usage_metadata.get("totalTokenCount", 0),
                usage_details=json.dumps(usage_details) if usage_details else None,
                prompt=prompt_log
            )
            return response_text
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Error from Google Gemini API: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                error_msg += f"\nResponse: {e.response.text}"
            prompt_log = json.dumps(payload, indent=2) if 'payload' in locals() else None
            self.log_interaction(message, error_msg, None, None, 0, None, prompt=prompt_log)
            raise Exception(error_msg)
            
        except Exception as e:
            error_msg = f"Error from Google Gemini API: {str(e)}"
            prompt_log = json.dumps(payload, indent=2) if 'payload' in locals() else None
            self.log_interaction(message, error_msg, None, None, 0, None, prompt=prompt_log)
            raise exception(error_msg)
            
        except Exception as e:
            error_msg = f"Error from Google Gemini API: {str(e)}"
            self.log_interaction(message, error_msg, None, None, 0, None)
            raise e


