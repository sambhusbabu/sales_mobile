"""HRMS routes for the Expo app.

List and detail screens call the same hrms.api functions the HRMS PWA calls.
Create, update, submit, and cancel go through the Frappe document API, so HR
permissions and workflows stay in HRMS.
"""

import frappe
from frappe import _
from frappe.utils import cint

import sales_mobile.documents as documents
from sales_mobile.access import parse_values, require_any_module, require_doctype, require_module
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
def get_doc(doctype: str, name: str):
	return documents.get_doc(doctype, name, HRMS_DOCTYPES)


@frappe.whitelist()
def get_form_fields(doctype: str):
	return documents.form_fields(doctype, HRMS_DOCTYPES)


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


@frappe.whitelist()
def get_current_employee_info():
	require_access_user()
	from hrms.api import get_current_employee_info as _fn

	return _fn()


def require_access_user():
	from sales_mobile.access import require_access

	return require_access()


@frappe.whitelist()
def get_hr_settings():
	require_access_user()
	from hrms.api import get_hr_settings as _fn

	return _fn()


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


@frappe.whitelist(methods=["POST"])
def apply_workflow(doc: dict | str, action: str):
	payload = frappe.parse_json(doc) if isinstance(doc, str) else doc
	if not isinstance(payload, dict) or not payload.get("doctype"):
		frappe.throw(_("Document is required"))
	_hrms(payload.get("doctype"))
	from frappe.model.workflow import apply_workflow as _fn

	return _fn(payload, action)
