import frappe
import json
from google import genai
from google.genai import types
from ai_assistant_app.ai_services.base import BaseAIService

class GeminiService(BaseAIService):
    def generate(self, text, prompt):
        client = genai.Client(api_key=self.api_key)
        system_instruction = "You are a helpful assistant. Always return JSON. The JSON should contain title, summary, hashtags (array of strings), and keywords (array of strings)."
        user_message = f"{prompt}\n\nDocument Text:\n{text}"
        
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json"
        )
        
        response = client.models.generate_content(
            model=self.model,
            contents=user_message,
            config=config
        )
        return response.text, {}

    def generate_response(self, message, enable_context=None):
        client = genai.Client(api_key=self.api_key)
        
        from ai_assistant_app.utils import ERPNextTools
        tools_manager = ERPNextTools()
        tools_manager.set_provider(self.provider_doc)

        tools = []
        if tools_manager.is_erpnext_context_enabled(enable_context):
            system_instruction = tools_manager.get_system_prompt(self.provider_doc)
            
            schema_dict = tools_manager.get_query_tool_schema()
            func_decl = types.FunctionDeclaration(
                name=schema_dict["name"],
                description=schema_dict["description"],
                parameters=schema_dict["parameters"]
            )
            tool = types.Tool(function_declarations=[func_decl])
            tools = [tool]
            
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=tools,
                temperature=0.7
            )
        else:
            config = types.GenerateContentConfig(
                system_instruction="You are a helpful assistant.",
                temperature=0.7
            )

        try:
            chat = client.chats.create(model=self.model, config=config)
            response = chat.send_message(message)
            response_text = response.text
            
            if response.function_calls:
                for func_call in response.function_calls:
                    if func_call.name == "query_erpnext_data":
                        args = func_call.args
                        tool_result = tools_manager.query_erpnext_data(
                            doctype=args.get("doctype"),
                            fields=args.get("fields"),
                            filters=args.get("filters")
                        )
                        response = chat.send_message(
                            types.Part.from_function_response(
                                name="query_erpnext_data",
                                response=tool_result
                            )
                        )
                        response_text = response.text
            
            usage_metadata = response.usage_metadata
            total_tokens = usage_metadata.total_token_count if usage_metadata else 0
            
            usage_details_dict = {}
            if usage_metadata:
                usage_details_dict = {
                    "prompt_token_count": getattr(usage_metadata, "prompt_token_count", 0),
                    "candidates_token_count": getattr(usage_metadata, "candidates_token_count", 0),
                    "total_token_count": getattr(usage_metadata, "total_token_count", 0)
                }
            usage_details_str = json.dumps(usage_details_dict) if usage_details_dict else None
            
            log_data = tools_manager.captured_data[0] if tools_manager.captured_data else None
            self.log_interaction(message, response_text, log_data, response.model_dump_json(), total_tokens, usage_details_str)
            
            return response_text
        except Exception as e:
            error_msg = f"Error from Google GenAI SDK: {str(e)}"
            self.log_interaction(message, error_msg, None, None, 0, None)
            raise e
