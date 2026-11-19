import re

import frappe
from frappe import _

from sales_mobile.registry import ALWAYS_FIELDS, DEFAULT_TABS, DOCTYPES, MODULES, READ_ONLY

_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def get_settings():
	"""Return Sales Mobile Settings. A missing single uses DocType defaults."""
	if frappe.db.exists("Sales Mobile Settings", "Sales Mobile Settings"):
		return frappe.get_cached_doc("Sales Mobile Settings")
	return frappe.get_doc({"doctype": "Sales Mobile Settings"})


def require_access():
	if frappe.session.user == "Guest":
		frappe.throw(_("Login required"), frappe.AuthenticationError)

	settings = get_settings()
	allowed = {row.role for row in (settings.allowed_roles or []) if row.role}
	if not allowed:
		return settings

	roles = set(frappe.get_roles())
	if "System Manager" in roles or "Administrator" in roles or not roles.isdisjoint(allowed):
		return settings

	frappe.throw(_("You are not allowed to use Sales Mobile"), frappe.PermissionError)


def require_module(module: str):
	settings = require_access()
	fieldname = MODULES.get(module)
	if not fieldname or not settings.get(fieldname):
		frappe.throw(_("{0} is turned off in Sales Mobile Settings").format(module), frappe.PermissionError)
	return settings


def require_any_module(*modules: str):
	settings = require_access()
	if any(settings.get(MODULES[module]) for module in modules if module in MODULES):
		return settings
	frappe.throw(_("This feature is turned off in Sales Mobile Settings"), frappe.PermissionError)


def require_doctype(doctype: str, allowed: dict):
	module = allowed.get(doctype)
	if not module:
		frappe.throw(_("{0} is not available in Sales Mobile").format(doctype), frappe.PermissionError)
	require_module(module)
	return module


def assert_writable(doctype: str):
	if doctype in READ_ONLY:
		frappe.throw(_("{0} is read only in Sales Mobile").format(doctype), frappe.PermissionError)


def configured_fieldnames(doctype: str, view: str) -> list[str]:
	settings = get_settings()
	names = []
	for row in settings.fields or []:
		if row.enabled and row.reference_doctype == doctype and row.view == view and row.fieldname:
			names.append(row.fieldname)
	return names


def list_columns(doctype: str):
	"""Columns for crm.api.doc.get_data. None means use the CRM default columns."""
	fieldnames = configured_fieldnames(doctype, "List")
	if not fieldnames:
		return None, None

	meta = frappe.get_meta(doctype)
	columns = []
	rows = []
	for fieldname in fieldnames:
		rows.append(fieldname)
		if fieldname in ALWAYS_FIELDS:
			columns.append({"label": fieldname.replace("_", " ").title(), "type": "Data", "key": fieldname})
			continue
		df = meta.get_field(fieldname)
		if not df:
			continue
		columns.append({"label": df.label or fieldname, "type": df.fieldtype, "key": fieldname})
	return columns, rows


def project(doctype: str, view: str, payload):
	"""Drop keys the field settings did not allow. No rows configured means return the payload."""
	allowed = configured_fieldnames(doctype, view)
	if not allowed:
		return payload
	keep = set(allowed) | ALWAYS_FIELDS
	if isinstance(payload, list):
		return [project(doctype, view, row) for row in payload]
	if isinstance(payload, dict):
		return {key: value for key, value in payload.items() if key in keep}
	return payload


def parse_values(values) -> dict:
	if isinstance(values, str):
		values = frappe.parse_json(values)
	if not isinstance(values, dict):
		frappe.throw(_("Invalid document values"))
	return dict(values)


def modules_payload(settings) -> dict:
	return {module: bool(settings.get(fieldname)) for module, fieldname in MODULES.items()}


def tabs_payload(settings) -> list[dict]:
	enabled = modules_payload(settings)
	rows = [row for row in (settings.tabs or []) if row.tab_key]
	if rows:
		source = [
			{
				"tab_key": row.tab_key,
				"label": row.label or row.tab_key,
				"module": row.module,
				"icon": row.icon,
				"show_on_home": bool(row.show_on_home),
				"enabled": bool(row.enabled),
			}
			for row in rows
			if row.enabled
		]
	else:
		source = [{**tab, "enabled": True} for tab in DEFAULT_TABS]

	return [tab for tab in source if enabled.get(tab["module"])]


def fields_payload(settings) -> dict:
	grouped = {}
	for row in settings.fields or []:
		if not row.enabled or not row.fieldname:
			continue
		grouped.setdefault(row.reference_doctype, {}).setdefault(row.view.lower(), []).append(
			{"fieldname": row.fieldname, "label": row.label or row.fieldname}
		)
	return grouped


def version_parts(value: str | None) -> tuple[int, ...]:
	parts = []
	for piece in str(value or "0").strip().split("."):
		digits = ""
		for char in piece:
			if char.isdigit():
				digits += char
			else:
				break
		parts.append(int(digits or 0))
	return tuple(parts) or (0,)


def version_is_older(current: str | None, target: str | None) -> bool:
	if not current or not target:
		return False
	left = version_parts(current)
	right = version_parts(target)
	width = max(len(left), len(right))
	left += (0,) * (width - len(left))
	right += (0,) * (width - len(right))
	return left < right


def update_payload(settings, platform: str | None, app_version: str | None) -> dict:
	platform = (platform or "").lower()
	if platform in ("ios", "iphone"):
		minimum = settings.ios_minimum_version or settings.minimum_app_version
		latest = settings.ios_latest_version
		store_url = settings.ios_store_url
	elif platform == "android":
		minimum = settings.android_minimum_version or settings.minimum_app_version
		latest = settings.android_latest_version
		store_url = settings.android_store_url
	else:
		minimum = settings.minimum_app_version
		latest = settings.ios_latest_version or settings.android_latest_version
		store_url = None

	below_minimum = version_is_older(app_version, minimum)
	return {
		"force": bool(settings.force_update and below_minimum),
		"update_available": below_minimum or version_is_older(app_version, latest),
		"minimum_version": minimum,
		"latest_version": latest,
		"store_url": store_url,
		"message": settings.update_message,
	}


def branding_payload(settings) -> dict:
	return {
		"app_name": settings.app_name or "Sales Mobile",
		"logo": settings.logo,
		"primary_color": settings.primary_color,
		"accent_color": settings.accent_color,
	}


def validate_color(value: str | None, label: str):
	if value and not _COLOR.match(value):
		frappe.throw(_("{0} must be a hex color such as #1F6FEB").format(label))


def known_doctype(doctype: str) -> bool:
	return doctype in DOCTYPES
