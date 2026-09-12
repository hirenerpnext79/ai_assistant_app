import frappe
from frappe import _
from ai_assistant_app.ai_services.gemini import GeminiService
from ai_assistant_app.ai_services.openrouter import OpenRouterService

PROVIDER_CLASSES = {
    "Gemini": GeminiService,
    "OpenRouter": OpenRouterService,
}


def _log_early_exit(user_query, response_message):
    """Store a log entry when the request exits before reaching an AI provider."""
    try:
        doc = frappe.get_doc({
            "doctype": "Akansha Log",
            "user": frappe.session.user,
            "user_query": user_query,
            "ai_response": response_message
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as ex:
        frappe.log_error(title="Akansha Early Exit Log Error", message=str(ex))


@frappe.whitelist()
def ask_akansha(message, context=None, enable_context=None, provider_name=None):
    if not _check_app_permission(message):
        return _("You do not have permission to use the AI Assistant.")

    if not message:
        return _("Please say something!")

    provider_doc = _get_and_validate_provider(provider_name, message)
    if isinstance(provider_doc, str):
        return provider_doc
        
    success, context_result = _validate_and_get_context(provider_doc, context, enable_context, message)
    if not success:
        return context_result
    enable_context = context_result

    if not _validate_api_key(provider_doc, message):
        msg = _("API Key is missing or masked as asterisks for {0}. Please re-enter it in settings.").format(provider_doc.name)
        return msg

    return process_ai_request(provider_doc, message, enable_context)

def _check_app_permission(message):
    if not frappe.has_permission("AI Assistant App Setting", "read"):
        _log_early_exit(message, _("You do not have permission to use the AI Assistant."))
        return False
    return True

def _get_and_validate_provider(provider_name, message):
    if not provider_name:
        provider_name = get_default_provider_name()
        if not provider_name:
            msg = _("No default AI Assistant Provider found. Please mark one provider as default.")
            _log_early_exit(message, msg)
            return msg

    provider_doc = get_active_provider_doc(provider_name)
    if provider_doc.error:
        _log_early_exit(message, provider_doc.error)
        return provider_doc.error

    if not is_user_allowed_for_provider(provider_doc):
        msg = _("You do not have permission to use the selected AI provider.")
        _log_early_exit(message, msg)
        return msg
        
    return provider_doc

def _validate_and_get_context(provider_doc, context, enable_context, message):
    if context:
        context_dict = frappe.parse_json(context) if isinstance(context, str) else context
        route = context_dict.get("route")

        current_doctype = None
        if route and isinstance(route, list) and len(route) >= 2 and route[0] in ("Form", "List", "Tree"):
            current_doctype = route[1]

        is_allowed, msg = check_doctype_permission(provider_doc, current_doctype)
        if not is_allowed:
            _log_early_exit(message, msg)
            return False, msg
        if msg == "disable_context":
            return True, 0
            
    return True, enable_context

def _validate_api_key(provider_doc, message):
    if not is_valid_api_key(provider_doc.get_password("api_key")):
        msg = _("API Key is missing or masked as asterisks for {0}. Please re-enter it in settings.").format(provider_doc.name)
        _log_early_exit(message, msg)
        return False
    return True


@frappe.whitelist()
def get_allowed_providers():
    if not frappe.has_permission("AI Assistant App Setting", "read"):
        return []

    try:
        providers = frappe.get_all(
            "AI Assistant Provider",
            filters={"status": "Active"},
            fields=["name", "provider_name", "is_default"]
        )

        user = frappe.session.user
        user_roles = set(frappe.get_roles(user))
        allowed = []

        for p in providers:
            doc = frappe.get_cached_doc("AI Assistant Provider", p.name)
            if is_user_allowed_for_provider(doc, user=user, user_roles=user_roles):
                allowed.append({
                    "name": doc.name,
                    "provider_name": doc.provider_name,
                    "is_default": doc.is_default
                })

        return allowed
    except Exception as e:
        frappe.log_error(title="get_allowed_providers Error", message=str(e))
        return []


def is_user_allowed_for_provider(provider_doc, user=None, user_roles=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return True

    allowed_users = {d.user for d in provider_doc.ai_assistant_user} if provider_doc.ai_assistant_user else set()
    allowed_roles = {d.role for d in provider_doc.ai_assistant_role} if provider_doc.ai_assistant_role else set()

    if not allowed_users and not allowed_roles:
        return False

    if user in allowed_users:
        return True

    user_roles = user_roles or set(frappe.get_roles(user))
    return bool(allowed_roles.intersection(user_roles))


def get_default_provider_name():
    return frappe.db.get_value(
        "AI Assistant Provider",
        {"is_default": 1, "status": "Active"},
        "name"
    )


def get_active_provider_doc(provider_name):
    provider_doc = frappe.get_doc("AI Assistant Provider", provider_name)
    provider_doc.error = None
    if provider_doc.status != "Active":
        provider_doc.error = _("The configured AI Assistant Provider is not active.")
    return provider_doc


def is_valid_api_key(api_key):
    if not api_key:
        return False
    val = str(api_key).strip()
    return bool(val) and val.lower() != "none" and set(val) != {"*"}


def process_ai_request(provider_doc, message, enable_context=None):
    service_instance = None
    try:
        service_class = PROVIDER_CLASSES.get(provider_doc.provider)
        if not service_class:
            return _("Selected provider is not supported for chat yet.")

        service_instance = service_class(provider_doc)
        response = service_instance.generate_response(message, enable_context)
        
        service_instance.log_interaction(message, response)
            
        return response

    except Exception as e:
        frappe.log_error(title="AI API Error", message=str(e))
        error_msg = _("An error occurred while contacting the AI provider: {0}").format(str(e))
        
        if service_instance:
            service_instance.log_error(message, error_msg)
        else:
            _log_early_exit(message, error_msg)
            
        return error_msg


@frappe.whitelist()
def get_chat_history():
    if not frappe.has_permission("AI Assistant App Setting", "read"):
        return []

    logs = frappe.get_all(
        "Akansha Log",
        filters={"user": frappe.session.user},
        fields=["user_query", "ai_response"],
        order_by="creation desc",
        limit=50
    )
    logs.reverse()
    return logs


@frappe.whitelist()
def get_all_allowed_doctypes(provider_doc, user=None):
    """
    Returns a set of all DocTypes the user has access to.
    Returns {"*"} if the user has access to all DocTypes.
    """
    user = user or frappe.session.user
    user_roles = set(frappe.get_roles(user))

    if not provider_doc.ai_doctype_permission:
        return {"*"}

    allowed_doctypes_collection = set()
    all_doctypes_allowed = False
    for perm_row in provider_doc.ai_doctype_permission:
        perm_name = perm_row.ai_doctype_permission
        if not perm_name:
            continue

        try:
            perm_doc = frappe.get_cached_doc("AI Assistant Permission", perm_name)
        except Exception:
            continue

        allowed_users = {d.user for d in perm_doc.ai_assistant_user} if perm_doc.ai_assistant_user else set()
        allowed_roles = {d.role for d in perm_doc.ai_assistant_role} if perm_doc.ai_assistant_role else set()

        has_access = (
            (not allowed_users and not allowed_roles) or 
            (user in allowed_users) or 
            bool(allowed_roles.intersection(user_roles))
        )

        if has_access:
            allowed_doctypes = {r.document_type for r in perm_doc.allowed_doctypes} if perm_doc.allowed_doctypes else set()
            if not allowed_doctypes:
                all_doctypes_allowed = True
                break
            else:
                allowed_doctypes_collection.update(allowed_doctypes)

    if all_doctypes_allowed:
        return {"*"}

    return allowed_doctypes_collection


def check_doctype_permission(provider_doc, doctype):
    if not doctype or not provider_doc.ai_doctype_permission:
        return True, ""

    allowed_doctypes = get_all_allowed_doctypes(provider_doc)
    
    if "*" in allowed_doctypes or doctype in allowed_doctypes:
        return True, ""

    return False, _('You do not have permission to access DocType "{0}"').format(doctype)
