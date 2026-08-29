import frappe
from frappe import _
from ai_assistant_app.ai_services.gemini import GeminiService

@frappe.whitelist()
def ask_alexa(message, context=None):
    if not message:
        return _("Please say something!")
    
    # 1. Fetch AI Assistant Provider (Gemini)
    provider = frappe.get_all(
        "AI Assistant Provider",
        filters={"provider": "Gemini", "status": "Active"},
        limit=1
    )
    
    if not provider:
        return _("Please configure an active Gemini AI Assistant Provider.")
        
    provider_doc = frappe.get_doc("AI Assistant Provider", provider[0].name)
    
    if not provider_doc.get_password("api_key"):
        return _("API Key is missing for the Gemini Provider.")
        
    try:
        service = GeminiService(provider_doc)
        return service.ask_alexa(message)
    except Exception as e:
        frappe.log_error(title="Gemini API Error", message=str(e))
        return _(f"An error occurred while contacting the AI provider: {str(e)}")

@frappe.whitelist()
def get_chat_history():
    logs = frappe.get_all(
        "Alexa Log",
        filters={"user": frappe.session.user},
        fields=["user_query", "ai_response"],
        order_by="creation desc",
        limit=50
    )
    
    logs.reverse()
    return logs
