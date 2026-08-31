import frappe
import json
from google import genai
from google.genai import types

class GeminiService:
    def __init__(self, provider_doc):
        self.api_key = (provider_doc.get_password("api_key") or "").strip()
        self.model = (provider_doc.model or "gemini-1.5-flash").strip()
        self.base_url = (provider_doc.base_url or "https://generativelanguage.googleapis.com/v1beta").strip()
        self.provider_doc = provider_doc

    def log_interaction(self, user_query, ai_response, response_data=None, api_response=None, usage_token=0, usage_details=None):
        try:
            doc = frappe.get_doc({
                "doctype": "Alexa Log",
                "user": frappe.session.user,
                "user_query": user_query,
                "ai_response": ai_response,
                "response_data": json.dumps(response_data) if response_data else None,
                "ai_api_response": api_response,
                "usage_token": usage_token,
                "usage_details": usage_details
            })
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(title="Alexa Log Error", message=str(e))

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

    def ask_alexa(self, message):
        client = genai.Client(api_key=self.api_key)
        
        from ai_assistant_app.utils import ERPNextTools
        tools_manager = ERPNextTools()
        query_erpnext_data = tools_manager.get_query_tool(self.provider_doc)

        if tools_manager.is_erpnext_context_enabled():
            system_instruction = tools_manager.get_system_prompt(self.provider_doc)
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=[query_erpnext_data],
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
