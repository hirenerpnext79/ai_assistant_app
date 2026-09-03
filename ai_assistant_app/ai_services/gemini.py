import frappe
import json
import requests
from ai_assistant_app.ai_services.base import BaseAIService

class GeminiService(BaseAIService):
    def get_api_url(self, action="generateContent"):
        return f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:{action}?key={self.api_key}"

    def generate(self, text, prompt):
        url = self.get_api_url()
        system_instruction = "You are a helpful assistant. Always return JSON. The JSON should contain title, summary, hashtags (array of strings), and keywords (array of strings)."
        user_message = f"{prompt}\n\nDocument Text:\n{text}"
        
        payload = {
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_message}]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
        
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        data = response.json()
        
        try:
            response_text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            response_text = ""
            
        return response_text, {}

    def generate_response(self, message, enable_context=None):
        url = self.get_api_url()
        
        from ai_assistant_app.utils import ERPNextTools
        tools_manager = ERPNextTools()
        tools_manager.set_provider(self.provider_doc)

        tools = []
        if tools_manager.is_erpnext_context_enabled(enable_context):
            system_instruction = tools_manager.get_system_prompt(self.provider_doc)
            schema_dict = tools_manager.get_query_tool_schema()
            tools = [
                {
                    "functionDeclarations": [
                        {
                            "name": schema_dict["name"],
                            "description": schema_dict["description"],
                            "parameters": schema_dict["parameters"]
                        }
                    ]
                }
            ]
        else:
            system_instruction = "You are a helpful assistant."

        contents = [
            {
                "role": "user",
                "parts": [{"text": message}]
            }
        ]
        
        payload = {
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7
            }
        }
        if tools:
            payload["tools"] = tools

        try:
            response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            data = response.json()
            
            candidate = data.get("candidates", [{}])[0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])
            
            response_text = ""
            function_calls = []
            
            for part in parts:
                if "text" in part:
                    response_text += part["text"]
                if "functionCall" in part:
                    function_calls.append(part["functionCall"])
                    
            if function_calls:
                # Add model response to contents
                contents.append({
                    "role": "model",
                    "parts": parts
                })
                
                # Handle all function calls and add responses
                function_responses = []
                for func_call in function_calls:
                    if func_call["name"] == "query_erpnext_data":
                        args = func_call.get("args", {})
                        tool_result = tools_manager.query_erpnext_data(
                            doctype=args.get("doctype"),
                            fields=args.get("fields"),
                            filters=args.get("filters")
                        )
                        function_responses.append({
                            "functionResponse": {
                                "name": "query_erpnext_data",
                                "response": tool_result if isinstance(tool_result, dict) else {"result": tool_result}
                            }
                        })
                
                contents.append({
                    "role": "function",
                    "parts": function_responses
                })
                
                # Send the second request with function responses
                response2 = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
                response2.raise_for_status()
                data2 = response2.json()
                
                candidate2 = data2.get("candidates", [{}])[0]
                content2 = candidate2.get("content", {})
                parts2 = content2.get("parts", [])
                
                response_text = ""
                for part in parts2:
                    if "text" in part:
                        response_text += part["text"]
                        
                # Use metadata from the final response
                data = data2

            usage_metadata = data.get("usageMetadata", {})
            total_tokens = usage_metadata.get("totalTokenCount", 0)
            
            usage_details_dict = {}
            if usage_metadata:
                usage_details_dict = {
                    "prompt_token_count": usage_metadata.get("promptTokenCount", 0),
                    "candidates_token_count": usage_metadata.get("candidatesTokenCount", 0),
                    "total_token_count": usage_metadata.get("totalTokenCount", 0)
                }
            usage_details_str = json.dumps(usage_details_dict) if usage_details_dict else None
            
            log_data = tools_manager.captured_data[0] if tools_manager.captured_data else None
            self.log_interaction(message, response_text, log_data, json.dumps(data), total_tokens, usage_details_str)
            
            return response_text
        except requests.exceptions.RequestException as e:
            error_msg = f"Error from Google Gemini API: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                error_msg += f"\nResponse: {e.response.text}"
            self.log_interaction(message, error_msg, None, None, 0, None)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Error from Google Gemini API: {str(e)}"
            self.log_interaction(message, error_msg, None, None, 0, None)
            raise e
