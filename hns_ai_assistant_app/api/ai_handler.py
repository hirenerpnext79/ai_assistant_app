import frappe
from frappe import _
from hns_ai_assistant_app.ai_services.gemini import GeminiService
from hns_ai_assistant_app.ai_services.openrouter import OpenRouterService

PROVIDER_CLASSES = {
    "Gemini": GeminiService,
    "OpenRouter": OpenRouterService,
}


def _log_early_exit(user_query, response_message, enable_context=None):
    try:
        doc = frappe.get_doc({
            "doctype": "Hns Akansha Log",
            "user": frappe.session.user,
            "user_query": user_query,
            "ai_response": response_message,
            "erpnext_context": 1 if frappe.utils.cint(enable_context) else 0
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as ex:
        frappe.log_error(title="Akansha Early Exit Log Error", message=str(ex))


@frappe.whitelist()
def ask_akansha(message, context=None, enable_context=None, provider_name=None):
    if not _check_app_permission(message, enable_context):
        return _("You do not have permission to use the AI Assistant.")

    if not message:
        return _("Please say something!")

    provider_doc = _get_and_validate_provider(provider_name, message, enable_context)
    if isinstance(provider_doc, str):
        return provider_doc

    success, context_result, current_doctype = _validate_and_get_context(provider_doc, context, enable_context, message)
    if not success:
        return context_result
    enable_context = context_result

    if not _validate_api_key(provider_doc, message, enable_context):
        return _("API Key is missing or masked as asterisks for {0}. Please re-enter it in settings.").format(provider_doc.name)

    return process_ai_request(provider_doc, message, enable_context)


def _check_app_permission(message, enable_context=None):
    if not frappe.has_permission("Hns AI Assistant App Setting", "read"):
        _log_early_exit(message, _("You do not have permission to use the AI Assistant."), enable_context)
        return False
    return True


def _get_and_validate_provider(provider_name, message, enable_context=None):
    if not provider_name:
        provider_name = get_default_provider_name()
        if not provider_name:
            msg = _("No default Hns AI Assistant Provider found. Please mark one provider as default.")
            _log_early_exit(message, msg, enable_context)
            return msg

    provider_doc = get_active_provider_doc(provider_name)
    if provider_doc.error:
        _log_early_exit(message, provider_doc.error, enable_context)
        return provider_doc.error

    if not is_user_allowed_for_provider(provider_doc):
        msg = _("You do not have permission to use the selected AI provider.")
        _log_early_exit(message, msg, enable_context)
        return msg

    return provider_doc


def _validate_and_get_context(provider_doc, context, enable_context, message):
    current_doctype = None
    if context:
        context_dict = frappe.parse_json(context) if isinstance(context, str) else context
        route = context_dict.get("route") if isinstance(context_dict, dict) else None

        if route and isinstance(route, list) and len(route) >= 2 and route[0] in ("Form", "List", "Tree"):
            current_doctype = route[1]

        is_allowed, msg = check_doctype_permission(provider_doc)
        if not is_allowed:
            _log_early_exit(message, msg, enable_context)
            return False, msg, current_doctype

    return True, enable_context, current_doctype


def _validate_api_key(provider_doc, message, enable_context=None):
    if not is_valid_api_key(provider_doc.get_password("api_key")):
        msg = _("API Key is missing or masked as asterisks for {0}. Please re-enter it in settings.").format(provider_doc.name)
        _log_early_exit(message, msg, enable_context)
        return False
    return True


@frappe.whitelist()
def get_allowed_providers():
    if not frappe.has_permission("Hns AI Assistant App Setting", "read"):
        return []

    try:
        providers = frappe.get_all(
            "Hns AI Assistant Provider",
            filters={"status": "Active"},
            fields=["name", "provider_name", "is_default"]
        )

        user = frappe.session.user
        user_roles = set(frappe.get_roles(user))
        allowed = []

        for p in providers:
            doc = frappe.get_cached_doc("Hns AI Assistant Provider", p.name)
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

    allowed_users = {d.user for d in provider_doc.hns_ai_assistant_user} if provider_doc.hns_ai_assistant_user else set()
    allowed_roles = {d.role for d in provider_doc.hns_ai_assistant_role} if provider_doc.hns_ai_assistant_role else set()

    if not allowed_users and not allowed_roles:
        return False

    if user in allowed_users:
        return True

    user_roles = user_roles or set(frappe.get_roles(user))
    return bool(allowed_roles.intersection(user_roles))


def get_default_provider_name():
    return frappe.db.get_value(
        "Hns AI Assistant Provider",
        {"is_default": 1, "status": "Active"},
        "name"
    )


def get_active_provider_doc(provider_name):
    provider_doc = frappe.get_doc("Hns AI Assistant Provider", provider_name)
    provider_doc.error = None
    if provider_doc.status != "Active":
        provider_doc.error = _("The configured Hns AI Assistant Provider is not active.")
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
        return service_instance.generate_response(message, enable_context)
    except Exception as e:
        frappe.log_error(title="AI API Error", message=str(e))

        if "API Error" in str(e):
            error_msg = str(e)
        else:
            error_msg = _("An error occurred while contacting the AI provider: {0}").format(str(e))

        if not service_instance:
            _log_early_exit(message, error_msg, enable_context)

        return error_msg


@frappe.whitelist()
def get_chat_history():
    if not frappe.has_permission("Hns AI Assistant App Setting", "read"):
        return []

    logs = frappe.get_all(
        "Hns Akansha Log",
        filters={"user": frappe.session.user},
        fields=["user_query", "ai_response", "creation"],
        order_by="creation desc",
        limit=50
    )
    logs.reverse()
    return logs


def get_matching_permissions_for_user(provider_doc, user=None):
    user = user or frappe.session.user
    provider_permissions = provider_doc.get("hns_ai_doctype_permission")
    if not provider_permissions:
        return None

    roles = set(frappe.get_roles(user))
    matching_permissions = []

    for row in provider_permissions:
        perm_name = row.hns_ai_doctype_permission
        if not perm_name:
            continue

        perm_doc = frappe.get_doc("Hns AI Assistant Permission", perm_name)

        if not perm_doc.hns_ai_assistant_user and not perm_doc.hns_ai_assistant_role:
            matching_permissions.append(perm_doc)
        elif any(u.user == user for u in perm_doc.hns_ai_assistant_user):
            matching_permissions.append(perm_doc)
        elif any(r.role in roles for r in perm_doc.hns_ai_assistant_role):
            matching_permissions.append(perm_doc)

    return matching_permissions


def check_doctype_permission(provider_doc, doctype=None):
    user = frappe.session.user
    matching_permissions = get_matching_permissions_for_user(provider_doc, user)

    if matching_permissions is None:
        if doctype and not frappe.db.exists("DocType", doctype):
            return False, _("DocType {0} does not exist.").format(doctype)
        if doctype and user != "Administrator" and not frappe.has_permission(doctype, "read", user=user):
            return False, _("You do not have permission to access {0} in ERPNext.").format(doctype)
        return True, ""

    if not matching_permissions:
        return False, _("No DocTypes are available for your user or role via this AI provider.")

    if not doctype:
        return True, ""

    allowed_doctypes = set()
    for perm_doc in matching_permissions:
        if not perm_doc.allowed_doctypes:
            if not frappe.db.exists("DocType", doctype):
                return False, _("DocType {0} does not exist.").format(doctype)
            if user != "Administrator" and not frappe.has_permission(doctype, "read", user=user):
                return False, _("You do not have permission to access {0} in ERPNext.").format(doctype)
            return True, ""

        for row in perm_doc.allowed_doctypes:
            if row.document_type:
                allowed_doctypes.add(row.document_type)

    if doctype in allowed_doctypes:
        if not frappe.db.exists("DocType", doctype):
            return False, _("DocType {0} does not exist.").format(doctype)
        if user != "Administrator" and not frappe.has_permission(doctype, "read", user=user):
            return False, _("You do not have permission to access {0} in ERPNext.").format(doctype)
        return True, ""

    if allowed_doctypes:
        available_list = "<br>".join(sorted(allowed_doctypes))
        return False, _("The {0} DocType is not available among the accessible DocTypes. The available DocTypes are:<br><br>{1}").format(doctype, available_list)

    return False, _("No DocTypes are currently available among the accessible DocTypes.")


def get_all_allowed_doctypes(provider_doc):
    user = frappe.session.user
    matching_permissions = get_matching_permissions_for_user(provider_doc, user)

    if matching_permissions is None:
        return ["*"]

    if not matching_permissions:
        return []

    allowed_doctypes = set()
    for perm_doc in matching_permissions:
        if not perm_doc.allowed_doctypes:
            return ["*"]

        for row in perm_doc.allowed_doctypes:
            if row.document_type:
                allowed_doctypes.add(row.document_type)

    return sorted(list(allowed_doctypes))
