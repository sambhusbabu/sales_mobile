"""App entry points for the Expo client.

Login stays on Frappe: POST /api/method/login, then call these methods with the
session cookie or an API token. CRM and HRMS methods are imported and called.
Their implementations are not copied and not overridden.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

from sales_mobile.access import (
	branding_payload,
	fields_payload,
	modules_payload,
	require_access,
	require_doctype,
	require_module,
	tabs_payload,
	update_payload,
)
from sales_mobile.registry import DOCTYPES


@frappe.whitelist()
def get_bootstrap(platform: str | None = None, app_version: str | None = None):
	"""One call for the Expo app start: user, employee, settings, and update rule."""
	settings = require_access()
	from hrms.api import get_current_employee_info, get_current_user_info

	from sales_mobile.api.hrms import hr_settings

	return {
		"user": get_current_user_info(),
		"employee": get_current_employee_info(),
		"hr_settings": hr_settings(),
		"branding": branding_payload(settings),
		"modules": modules_payload(settings),
		"tabs": tabs_payload(settings),
		"fields": fields_payload(settings),
		"update": update_payload(settings, platform, app_version),
		"push": {"enabled": bool(settings.enable_push_notifications)},
	}


@frappe.whitelist(methods=["POST"])
def register_device(expo_push_token: str, platform: str, app_version: str | None = None):
	settings = require_access()
	if not settings.enable_push_notifications:
		frappe.throw(_("Push notifications are turned off in Sales Mobile Settings"))
	if platform not in ("iOS", "Android"):
		frappe.throw(_("Platform must be iOS or Android"))
	if not expo_push_token:
		frappe.throw(_("Expo push token is required"))

	name = frappe.db.get_value("Sales Mobile Device", {"expo_push_token": expo_push_token}, "name")
	values = {
		"user": frappe.session.user,
		"platform": platform,
		"app_version": app_version,
		"last_seen": now_datetime(),
	}
	if name:
		frappe.db.set_value("Sales Mobile Device", name, values)
		return {"name": name}

	doc = frappe.get_doc({"doctype": "Sales Mobile Device", "expo_push_token": expo_push_token, **values})
	doc.insert(ignore_permissions=True)
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def unregister_device(expo_push_token: str):
	require_access()
	name = frappe.db.get_value(
		"Sales Mobile Device",
		{"expo_push_token": expo_push_token, "user": frappe.session.user},
		"name",
	)
	if name:
		frappe.delete_doc("Sales Mobile Device", name, ignore_permissions=True)
	return {"ok": True}


@frappe.whitelist()
def search_link(
	doctype: str,
	txt: str = "",
	filters: str | dict | list | None = None,
	page_length: int = 10,
	searchfield: str | None = None,
	reference_doctype: str | None = None,
	start: int = 0,
):
	"""Link-field search. User permissions are never ignored."""
	require_access()
	if doctype in DOCTYPES:
		require_module(DOCTYPES[doctype])
	if reference_doctype in DOCTYPES:
		require_doctype(reference_doctype, DOCTYPES)

	from frappe.desk.search import search_link as _search_link

	return _search_link(
		doctype,
		txt,
		filters=filters,
		page_length=page_length,
		searchfield=searchfield,
		reference_doctype=reference_doctype,
		ignore_user_permissions=False,
		start=start,
	)
