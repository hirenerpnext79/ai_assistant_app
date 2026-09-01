import frappe
from frappe import _
from ai_assistant_app.ai_services.gemini import GeminiService
from ai_assistant_app.ai_services.openrouter import OpenRouterService

PROVIDER_CLASSES = {
    "Gemini": GeminiService,
    "OpenRouter": OpenRouterService
}

@frappe.whitelist()
def ask_alexa(message, context=None, enable_context=None):
    if not message:
        return _("Please say something!")
    
    provider_name = get_default_provider_name()
    if not provider_name:
        return _("Please configure a default AI Assistant Provider in AI Assistant App Setting.")
        
    provider_doc = get_active_provider_doc(provider_name)
    if provider_doc.error:
        return provider_doc.error
        
    if not is_valid_api_key(provider_doc.get_password("api_key")):
        return _(f"API Key is missing or masked as asterisks for {provider_doc.name}. Please re-enter it in settings.")
        
    return process_ai_request(provider_doc, message, enable_context)

def get_default_provider_name():
    return frappe.db.get_single_value("AI Assistant App Setting", "ai_assistant_provider")

def get_active_provider_doc(provider_name):
    provider_doc = frappe.get_doc("AI Assistant Provider", provider_name)
    provider_doc.error = None
    if provider_doc.status != "Active":
        provider_doc.error = _("The configured default AI Assistant Provider is not active.")
    return provider_doc

def is_valid_api_key(api_key):
    if not api_key:
        return False
    val = str(api_key).strip()
    return bool(val) and val.lower() != "none" and set(val) != {"*"}

def process_ai_request(provider_doc, message, enable_context=None):
    try:
        service_class = PROVIDER_CLASSES.get(provider_doc.provider)
        if not service_class:
            return _("Selected provider is not supported for chat yet.")
            
        service = service_class(provider_doc)
        return service.generate_response(message, enable_context)
            
    except Exception as e:
        frappe.log_error(title="AI API Error", message=str(e))
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
