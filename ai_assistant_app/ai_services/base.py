import frappe
import json

class BaseAIService:
    def __init__(self, provider_doc):
        self.provider_doc = provider_doc
        self.model = provider_doc.model
        self.base_url = provider_doc.base_url
        self.api_key = (provider_doc.get_password("api_key") or "").strip()

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

    def generate_response(self, message, enable_context=None):
        raise NotImplementedError("This method must be implemented by subclasses.")
