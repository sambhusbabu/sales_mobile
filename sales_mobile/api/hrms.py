"""HRMS routes for the Expo app.

List and detail screens call the same hrms.api functions the HRMS PWA calls.
Create, update, submit, and cancel go through the Frappe document API, so HR
permissions and workflows stay in HRMS.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, get_first_day, get_last_day, nowdate

import sales_mobile.documents as documents
from sales_mobile.access import (
	configured_fieldnames,
	parse_values,
	require_any_module,
	require_doctype,
	require_module,
)
from sales_mobile.registry import HRMS_DOCTYPES, NOTIFICATION_FIELDS


def _hrms(doctype: str):
	require_doctype(doctype, HRMS_DOCTYPES)


@frappe.whitelist()
def get_list(
	doctype: str,
	filters: dict | str | None = None,
	order_by: str = "modified desc",
	page_length: int = 20,
	start: int = 0,
):
	return documents.get_list(doctype, HRMS_DOCTYPES, filters, order_by, page_length, start)


@frappe.whitelist()
def get_list_filters(doctype: str):
	"""Filter fields for an HR list. Standard list filters, plus document status when the DocType is submittable."""
	_hrms(doctype)
	return documents.list_filters(doctype)


@frappe.whitelist()
def get_doc(doctype: str, name: str):
	return documents.get_doc(doctype, name, HRMS_DOCTYPES)


@frappe.whitelist()
def get_activities(doctype: str, name: str):
	"""Full timeline for an HR document, in the same shape as a CRM timeline."""
	from sales_mobile.activities import document_activity

	return document_activity(doctype, name, HRMS_DOCTYPES)


@frappe.whitelist()
def get_form_fields(doctype: str):
	"""Tabs, sections, and columns from the HR form, in the same shape as CRM."""
	_hrms(doctype)
	from hrms.api import SUPPORTED_FIELD_TYPES

	meta = frappe.get_meta(doctype)
	draft = frappe.new_doc(doctype)
	return documents.layout_with_values(
		documents.meta_layout(doctype),
		draft,
		1 if meta.is_submittable else 0,
		set(configured_fieldnames(doctype, "Detail")),
		fieldtypes=set(SUPPORTED_FIELD_TYPES),
		skip_fieldnames={"amended_from"},
	)


@frappe.whitelist()
def get_doc_permissions(doctype: str, name: str):
	return documents.doc_permissions(doctype, name, HRMS_DOCTYPES)


@frappe.whitelist()
def has_permission(doctype: str, name: str = "", perm_type: str = "read"):
	return documents.has_permission(doctype, name, perm_type, HRMS_DOCTYPES)


@frappe.whitelist(methods=["POST"])
def create_doc(doctype: str, values: dict | str):
	if doctype == "PWA Notification":
		frappe.throw(_("Notifications cannot be created from Sales Mobile"), frappe.PermissionError)
	if doctype == "Employee Checkin":
		values = apply_checkin_rules(parse_values(values))
	return documents.create_doc(doctype, values, HRMS_DOCTYPES)


@frappe.whitelist(methods=["POST"])
def update_doc(doctype: str, name: str, values: dict | str):
	if doctype == "PWA Notification":
		require_module("notifications")
		payload = parse_values(values)
		if set(payload) - NOTIFICATION_FIELDS:
			frappe.throw(_("Only the read field can be updated on a notification"))
		owner = frappe.db.get_value("PWA Notification", name, "to_user")
		if owner != frappe.session.user:
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		frappe.db.set_value("PWA Notification", name, "read", cint(payload.get("read")), update_modified=False)
		return documents.get_doc(doctype, name, HRMS_DOCTYPES)
	return documents.update_doc(doctype, name, values, HRMS_DOCTYPES)


@frappe.whitelist(methods=["POST"])
def delete_doc(doctype: str, name: str):
	if doctype == "PWA Notification":
		frappe.throw(_("Notifications cannot be deleted from Sales Mobile"), frappe.PermissionError)
	return documents.delete_doc(doctype, name, HRMS_DOCTYPES)


@frappe.whitelist(methods=["POST"])
def submit_doc(doctype: str, name: str):
	return documents.submit_doc(doctype, name, HRMS_DOCTYPES)


@frappe.whitelist(methods=["POST"])
def cancel_doc(doctype: str, name: str):
	return documents.cancel_doc(doctype, name, HRMS_DOCTYPES)


@frappe.whitelist()
def get_current_user_info():
	require_access_user()
	from hrms.api import get_current_user_info as _fn

	return _fn()


_USER_SECTIONS = (
	{
		"key": "user",
		"title": "User",
		"fields": (
			"full_name",
			"first_name",
			"middle_name",
			"last_name",
			"username",
			"email",
			"gender",
			"birth_date",
		),
	},
	{
		"key": "contact",
		"title": "Contact",
		"fields": ("mobile_no", "phone", "location"),
	},
	{
		"key": "preferences",
		"title": "Preferences",
		"fields": ("language", "time_zone", "bio", "interest"),
	},
)


@frappe.whitelist()
def get_user_profile():
	"""Display fields for the logged-in User. Password and API secrets are not included."""
	require_access_user()
	fieldnames = [fieldname for section in _USER_SECTIONS for fieldname in section["fields"]]
	row = frappe.db.get_value("User", frappe.session.user, ["name", "user_image", *fieldnames], as_dict=True) or {}
	meta = frappe.get_meta("User")
	sections = []
	for section in _USER_SECTIONS:
		fields = []
		for fieldname in section["fields"]:
			df = meta.get_field(fieldname)
			fields.append(
				{
					"fieldname": fieldname,
					"label": df.label if df else fieldname,
					"fieldtype": df.fieldtype if df else "Data",
					"value": row.get(fieldname),
				}
			)
		sections.append({"key": section["key"], "title": section["title"], "fields": fields})

	return {
		"name": row.get("name") or frappe.session.user,
		"full_name": row.get("full_name"),
		"user_image": row.get("user_image"),
		"roles": frappe.get_roles(),
		"sections": sections,
	}


@frappe.whitelist()
def get_current_employee_info():
	require_access_user()
	from hrms.api import get_current_employee_info as _fn

	return _fn()


def require_access_user():
	from sales_mobile.access import require_access

	return require_access()


def hr_settings() -> dict:
	"""HR Settings flags the PWA reads. Geolocation is enforced on check-in."""
	from hrms.api import get_hr_settings as _fn

	raw = _fn()
	return {
		"allow_employee_checkin_from_mobile_app": bool(raw.allow_employee_checkin_from_mobile_app),
		"allow_geolocation_tracking": bool(raw.allow_geolocation_tracking),
		"prevent_self_leave_approval": bool(raw.prevent_self_leave_approval),
		"enable_multi_currency_expense_claim": bool(raw.enable_multi_currency_expense_claim),
	}


def apply_checkin_rules(values: dict) -> dict:
	"""Match Employee Checkin.validate_distance_from_shift_location.

	When Allow Geolocation Tracking is on, latitude and longitude are required.
	HRMS then rejects a punch outside the shift location radius. When it is off,
	coordinates are dropped.
	"""
	settings = hr_settings()
	if not settings["allow_employee_checkin_from_mobile_app"]:
		frappe.throw(_("Check-in from the mobile app is turned off in HR Settings"))

	values = dict(values)
	if settings["allow_geolocation_tracking"]:
		if not values.get("latitude") and not values.get("longitude"):
			frappe.throw(_("Latitude and longitude values are required for checking in."))
	else:
		values.pop("latitude", None)
		values.pop("longitude", None)
		values.pop("geolocation", None)
	return values


def _module_enabled(module: str) -> bool:
	from sales_mobile.access import get_settings
	from sales_mobile.registry import MODULES

	return bool(get_settings().get(MODULES[module]))


def _current_employee() -> str | None:
	from hrms.api import get_current_employee

	try:
		return get_current_employee()
	except frappe.PermissionError:
		return None


def _leave_balance_chart():
	from hrms.api import get_leave_balance_map

	rows = []
	for leave_type, allocation in (get_leave_balance_map() or {}).items():
		allocated = flt(allocation.get("allocated_leaves"))
		balance = flt(allocation.get("balance_leaves"))
		rows.append(
			{
				"leave_type": leave_type,
				"allocated_leaves": allocated,
				"balance_leaves": balance,
				"balance_percentage": (balance / allocated * 100) if allocated else 0,
			}
		)
	return {
		"name": "leave_balance",
		"type": "donut_chart",
		"title": _("Leave balance"),
		"categoryColumn": "leave_type",
		"valueColumn": "balance_leaves",
		"data": rows,
	}


def _expense_chart():
	from hrms.api import get_expense_claim_summary

	summary = get_expense_claim_summary()
	approved = flt(summary.get("total_approved_amount"))
	rejected = flt(summary.get("total_rejected_amount")) + (
		flt(summary.get("total_claimed_in_approved")) - approved
	)
	return {
		"name": "expense_claim_summary",
		"type": "donut_chart",
		"title": _("Expense claim summary"),
		"currency": summary.get("currency"),
		"categoryColumn": "status",
		"valueColumn": "amount",
		"data": [
			{"status": "Pending", "amount": flt(summary.get("total_pending_amount"))},
			{"status": "Approved", "amount": approved},
			{"status": "Rejected", "amount": rejected},
		],
	}


def _attendance_chart():
	from hrms.api import get_attendance_calendar_events

	start = get_first_day(nowdate())
	end = get_last_day(nowdate())
	counts: dict[str, int] = {}
	for status in (get_attendance_calendar_events(start, end) or {}).values():
		counts[status] = counts.get(status, 0) + 1
	return {
		"name": "attendance_this_month",
		"type": "donut_chart",
		"title": _("Attendance this month"),
		"categoryColumn": "status",
		"valueColumn": "count",
		"data": [{"status": status, "count": count} for status, count in counts.items()],
	}


def _salary_chart(employee: str):
	slip = frappe.get_list(
		"Salary Slip",
		filters={"employee": employee, "docstatus": 1},
		fields=["year_to_date", "net_pay", "currency", "end_date"],
		order_by="end_date desc",
		limit=1,
	)
	if not slip:
		return None
	row = slip[0]
	return {
		"name": "salary_year_to_date",
		"type": "number_chart",
		"title": _("Year to date"),
		"value": flt(row.year_to_date),
		"suffix": row.currency,
		"net_pay": flt(row.net_pay),
		"end_date": row.end_date,
	}


@frappe.whitelist()
def get_home_charts():
	"""Charts for the HR home page. Each item uses the same shape as a CRM chart."""
	require_access_user()
	employee = _current_employee()
	charts = []
	if employee and _module_enabled("leave"):
		charts.append(_leave_balance_chart())
	if employee and _module_enabled("expense_claim"):
		charts.append(_expense_chart())
	if employee and _module_enabled("attendance"):
		charts.append(_attendance_chart())
	if employee and _module_enabled("salary_slip"):
		salary = _salary_chart(employee)
		if salary:
			charts.append(salary)
	return charts


@frappe.whitelist()
def get_hr_settings():
	require_access_user()
	return hr_settings()


@frappe.whitelist(methods=["POST"])
def employee_checkin(
	log_type: str,
	time: str,
	latitude: float | str | None = None,
	longitude: float | str | None = None,
	device_id: str | None = None,
):
	"""Punch IN or OUT for the logged-in employee."""
	require_module("attendance")
	from hrms.api import get_current_employee_info

	employee = get_current_employee_info()
	if not employee:
		frappe.throw(_("Employee not found"), frappe.PermissionError)

	values = apply_checkin_rules(
		{
			"employee": employee.name,
			"log_type": log_type,
			"time": time,
			"latitude": latitude,
			"longitude": longitude,
			"device_id": device_id,
		}
	)
	return documents.create_doc("Employee Checkin", values, HRMS_DOCTYPES)


@frappe.whitelist()
def get_all_employees():
	require_module("hrms_home")
	from hrms.api import get_all_employees as _fn

	return _fn()


@frappe.whitelist()
def get_reports_to_employee_name(employee: str):
	require_module("profile")
	from hrms.api import get_reports_to_employee_name as _fn

	return _fn(employee)


_PROFILE_SECTIONS = (
	{
		"key": "employee_details",
		"title": "Employee Details",
		"icon": "user",
		"fields": (
			"employee_name",
			"employee_number",
			"gender",
			"date_of_birth",
			"date_of_joining",
			"blood_group",
		),
	},
	{
		"key": "company",
		"title": "Company Information",
		"icon": "file-text",
		"fields": (
			"company",
			"department",
			"designation",
			"branch",
			"grade",
			"reports_to",
			"employment_type",
		),
	},
	{
		"key": "contact",
		"title": "Contact Information",
		"icon": "contact",
		"fields": ("cell_number", "personal_email", "company_email", "preferred_email"),
	},
	{
		"key": "salary",
		"title": "Salary Information",
		"icon": "banknote",
		"fields": (
			"ctc",
			"payroll_cost_center",
			"pan_number",
			"provident_fund_account",
			"salary_mode",
			"bank_name",
			"bank_ac_no",
			"ifsc_code",
			"micr_code",
			"iban",
		),
	},
)


@frappe.whitelist()
def get_employee_profile():
	"""The HRMS profile page: the logged-in employee's details, grouped like the PWA."""
	require_module("profile")
	from hrms.api import get_current_employee_info, get_reports_to_employee_name

	info = get_current_employee_info()
	if not info:
		frappe.throw(_("Employee not found"), frappe.PermissionError)

	doc = frappe.get_doc("Employee", info.name)
	meta = frappe.get_meta("Employee")
	reports_to = get_reports_to_employee_name(doc.reports_to) if doc.reports_to else None
	user = frappe.db.get_value(
		"User",
		frappe.session.user,
		["full_name", "first_name", "user_image"],
		as_dict=True,
	) or {}

	sections = []
	for section in _PROFILE_SECTIONS:
		rows = []
		for fieldname in section["fields"]:
			df = meta.get_field(fieldname)
			if not df:
				continue
			value = doc.get(fieldname)
			if fieldname == "employee_number" and not value:
				value = doc.name
			if fieldname == "reports_to" and reports_to:
				value = reports_to
			rows.append(
				{
					"fieldname": fieldname,
					"label": df.label,
					"fieldtype": df.fieldtype,
					"value": value,
				}
			)
		sections.append({"key": section["key"], "title": section["title"], "icon": section["icon"], "fields": rows})

	return {
		"name": doc.name,
		"employee_name": doc.employee_name,
		"designation": doc.designation,
		"image": doc.image or user.get("user_image"),
		"salary_currency": doc.salary_currency,
		"sections": sections,
	}


@frappe.whitelist()
def get_attendance_calendar_events(from_date: str, to_date: str):
	require_module("attendance")
	from hrms.api import get_attendance_calendar_events as _fn

	return _fn(from_date, to_date)


@frappe.whitelist()
def get_shift_requests(
	employee: str,
	approver_id: str | None = None,
	for_approval: bool = False,
	limit: int | None = None,
):
	require_module("attendance")
	from hrms.api import get_shift_requests as _fn

	return _fn(employee, approver_id, for_approval, limit)


@frappe.whitelist()
def get_attendance_requests(employee: str, for_approval: bool = False, limit: int | None = None):
	require_module("attendance")
	from hrms.api import get_attendance_requests as _fn

	return _fn(employee, for_approval, limit)


@frappe.whitelist()
def get_shift_request_approvers(employee: str):
	require_module("attendance")
	from hrms.api import get_shift_request_approvers as _fn

	return _fn(employee)


@frappe.whitelist()
def get_shifts():
	require_module("attendance")
	from hrms.api import get_shifts as _fn

	return _fn()


@frappe.whitelist()
def get_leave_applications(
	employee: str,
	approver_id: str | None = None,
	for_approval: bool = False,
	limit: int | None = None,
):
	require_module("leave")
	from hrms.api import get_leave_applications as _fn

	return _fn(employee, approver_id, for_approval, limit)


@frappe.whitelist()
def get_leave_balance_map():
	require_module("leave")
	from hrms.api import get_leave_balance_map as _fn

	return _fn()


@frappe.whitelist()
def get_holidays_for_employee(employee: str):
	require_module("leave")
	from hrms.api import get_holidays_for_employee as _fn

	return _fn(employee)


@frappe.whitelist()
def get_leave_approval_details(employee: str):
	require_module("leave")
	from hrms.api import get_leave_approval_details as _fn

	return _fn(employee)


@frappe.whitelist()
def get_leave_types(employee: str, date: str):
	require_module("leave")
	from hrms.api import get_leave_types as _fn

	return _fn(employee, date)


@frappe.whitelist()
def get_number_of_leave_days(
	employee: str,
	leave_type: str,
	from_date: str,
	to_date: str,
	half_day: int | str | None = None,
	half_day_date: str | None = None,
	holiday_list: str | None = None,
	leave_application: str | None = None,
):
	require_module("leave")
	from hrms.hr.doctype.leave_application.leave_application import get_number_of_leave_days as _fn

	return _fn(
		employee,
		leave_type,
		from_date,
		to_date,
		half_day,
		half_day_date,
		holiday_list,
		leave_application,
	)


@frappe.whitelist()
def get_leave_balance_on(
	employee: str,
	leave_type: str,
	date: str,
	to_date: str | None = None,
	consider_all_leaves_in_the_allocation_period: bool = False,
	for_consumption: bool = False,
	leave_application: str | None = None,
):
	require_module("leave")
	from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on as _fn

	return _fn(
		employee,
		leave_type,
		date,
		to_date,
		consider_all_leaves_in_the_allocation_period,
		for_consumption,
		leave_application,
	)


@frappe.whitelist()
def get_expense_claims(
	employee: str,
	approver_id: str | None = None,
	for_approval: bool = False,
	limit: int | None = None,
):
	require_module("expense_claim")
	from hrms.api import get_expense_claims as _fn

	return _fn(employee, approver_id, for_approval, limit)


@frappe.whitelist()
def get_expense_claim_summary():
	require_module("expense_claim")
	from hrms.api import get_expense_claim_summary as _fn

	return _fn()


@frappe.whitelist()
def get_expense_type_description(expense_type: str):
	require_module("expense_claim")
	from hrms.api import get_expense_type_description as _fn

	return _fn(expense_type)


@frappe.whitelist()
def get_expense_claim_types():
	require_module("expense_claim")
	from hrms.api import get_expense_claim_types as _fn

	return _fn()


@frappe.whitelist()
def get_expense_approval_details(employee: str):
	require_module("expense_claim")
	from hrms.api import get_expense_approval_details as _fn

	return _fn(employee)


@frappe.whitelist()
def get_company_cost_center_and_expense_account(company: str):
	require_module("expense_claim")
	from hrms.api import get_company_cost_center_and_expense_account as _fn

	return _fn(company)


@frappe.whitelist()
def get_advances(expense_claim: str | dict, advance_id: str | None = None):
	require_module("expense_claim")
	from hrms.hr.doctype.expense_claim.expense_claim import get_advances as _fn

	return _fn(expense_claim, advance_id)


@frappe.whitelist()
def get_exchange_rate(from_currency: str, to_currency: str, transaction_date: str | None = None, args=None):
	require_any_module("expense_claim", "salary_slip", "employee_advance")
	from erpnext.setup.utils import get_exchange_rate as _fn

	return _fn(from_currency, to_currency, transaction_date, args)


@frappe.whitelist()
def get_employee_advance_balance():
	require_module("employee_advance")
	from hrms.api import get_employee_advance_balance as _fn

	return _fn()


@frappe.whitelist()
def get_company_currencies():
	require_any_module("expense_claim", "salary_slip", "employee_advance")
	from hrms.api import get_company_currencies as _fn

	return _fn()


@frappe.whitelist()
def get_currency_symbols():
	require_any_module("expense_claim", "salary_slip", "employee_advance")
	from hrms.api import get_currency_symbols as _fn

	return _fn()


@frappe.whitelist()
def download_pdf(doctype: str, docname: str):
	_hrms(doctype)
	from hrms.api import _download_pdf

	return _download_pdf(doctype, docname)


@frappe.whitelist()
def get_unread_notifications_count():
	require_module("notifications")
	from hrms.api import get_unread_notifications_count as _fn

	return _fn()


@frappe.whitelist(methods=["POST"])
def mark_all_notifications_as_read():
	require_module("notifications")
	from hrms.api import mark_all_notifications_as_read as _fn

	return _fn()


@frappe.whitelist()
def get_doctype_fields(doctype: str):
	_hrms(doctype)
	from sales_mobile.access import configured_fieldnames
	from hrms.api import get_doctype_fields as _fn

	fields = _fn(doctype)
	allowed = set(configured_fieldnames(doctype, "Detail"))
	if not allowed:
		return fields
	return [field for field in fields if field.fieldname in allowed]


@frappe.whitelist()
def get_doctype_states(doctype: str):
	_hrms(doctype)
	from hrms.api import get_doctype_states as _fn

	return _fn(doctype)


@frappe.whitelist()
def get_attachments(dt: str, dn: str):
	_hrms(dt)
	from hrms.api import get_attachments as _fn

	return _fn(dt, dn)


@frappe.whitelist(methods=["POST"])
def upload_base64_file(
	content: str,
	filename: str,
	dt: str | None = None,
	dn: str | None = None,
	fieldname: str | None = None,
):
	if dt:
		_hrms(dt)
	else:
		require_access_user()
	from hrms.api import upload_base64_file as _fn

	return _fn(content, filename, dt, dn, fieldname)


@frappe.whitelist(methods=["POST"])
def delete_attachment(filename: str):
	attached = frappe.db.get_value("File", filename, ["attached_to_doctype", "attached_to_name"])
	if attached and attached[0] in HRMS_DOCTYPES:
		_hrms(attached[0])
	else:
		require_access_user()
	from hrms.api import delete_attachment as _fn

	return _fn(filename)


@frappe.whitelist()
def get_workflow(doctype: str):
	_hrms(doctype)
	from hrms.api import get_workflow as _fn

	return _fn(doctype)


@frappe.whitelist()
def get_permitted_fields_for_write(doctype: str):
	_hrms(doctype)
	from hrms.api import get_permitted_fields_for_write as _fn

	return _fn(doctype)


@frappe.whitelist()
def get_transitions(doc: dict | str):
	payload = frappe.parse_json(doc) if isinstance(doc, str) else doc
	if not isinstance(payload, dict) or not payload.get("doctype"):
		frappe.throw(_("Document is required"))
	_hrms(payload.get("doctype"))
	from frappe.model.workflow import get_transitions as _fn

	return _fn(payload)


@frappe.whitelist()
def get_value(
	doctype: str,
	fieldname: str | list | dict,
	filters: str | list | dict | None = None,
	as_dict: int | bool = True,
):
	"""Same lookup the expense form uses for Employee.salary_currency."""
	_hrms(doctype)
	from frappe.client import get_value as _fn

	return _fn(doctype, fieldname, filters, as_dict=as_dict)


@frappe.whitelist(allow_guest=True)
def get_user_pass_login_disabled():
	from hrms.api.system_settings import get_user_pass_login_disabled as _fn

	return _fn()


@frappe.whitelist(methods=["POST"])
def update_password(new_password: str, old_password: str, logout_all_sessions: int = 0):
	require_access_user()
	from frappe.core.doctype.user.user import update_password as _fn

	return _fn(new_password, logout_all_sessions=logout_all_sessions, old_password=old_password)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def reset_password(user: str):
	from frappe.core.doctype.user.user import reset_password as _fn

	return _fn(user)


@frappe.whitelist()
def are_push_notifications_enabled():
	"""Frappe web-push relay flag used by the HRMS PWA. Expo push is `push.enabled` on bootstrap."""
	require_access_user()
	from hrms.api import are_push_notifications_enabled as _fn

	return _fn()


@frappe.whitelist(methods=["POST"])
def apply_workflow(doc: dict | str, action: str):
	payload = frappe.parse_json(doc) if isinstance(doc, str) else doc
	if not isinstance(payload, dict) or not payload.get("doctype"):
		frappe.throw(_("Document is required"))
	_hrms(payload.get("doctype"))
	from frappe.model.workflow import apply_workflow as _fn

	return _fn(payload, action)
