"""CRM routes for the Expo app.

Each method checks Sales Mobile Settings, then calls the existing CRM function
or the Frappe document API. Nothing in the CRM app is overridden.
"""

import frappe
from frappe import _

import sales_mobile.documents as documents
from sales_mobile.access import list_columns, project, require_access, require_doctype, require_module
from sales_mobile.registry import CRM_DOCTYPES


def _crm(doctype: str):
	require_doctype(doctype, CRM_DOCTYPES)


@frappe.whitelist()
def get_list(
	doctype: str,
	filters: dict | str | None = None,
	order_by: str = "modified desc",
	page_length: int = 20,
	page_length_count: int = 20,
	default_filters: dict | str | None = None,
):
	"""List view. Routes to crm.api.doc.get_data, which the CRM frontend uses."""
	_crm(doctype)
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	columns, rows = list_columns(doctype)
	from crm.api.doc import get_data

	result = get_data(
		doctype=doctype,
		filters=filters or {},
		order_by=order_by or "modified desc",
		page_length=page_length,
		page_length_count=page_length_count,
		columns=columns,
		rows=rows,
		default_filters=default_filters,
	)
	if columns:
		result["data"] = project(doctype, "List", result.get("data") or [])
	return result


@frappe.whitelist()
def get_doc(doctype: str, name: str):
	return documents.get_doc(doctype, name, CRM_DOCTYPES)


@frappe.whitelist()
def get_form_fields(doctype: str):
	return documents.form_fields(doctype, CRM_DOCTYPES)


@frappe.whitelist()
def get_doc_permissions(doctype: str, name: str):
	return documents.doc_permissions(doctype, name, CRM_DOCTYPES)


@frappe.whitelist(methods=["POST"])
def create_doc(doctype: str, values: dict | str):
	return documents.create_doc(doctype, values, CRM_DOCTYPES)


@frappe.whitelist(methods=["POST"])
def update_doc(doctype: str, name: str, values: dict | str):
	return documents.update_doc(doctype, name, values, CRM_DOCTYPES)


@frappe.whitelist(methods=["POST"])
def delete_doc(doctype: str, name: str):
	return documents.delete_doc(doctype, name, CRM_DOCTYPES)


@frappe.whitelist()
def get_dashboard(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	require_module("dashboard")
	from crm.api.dashboard import get_dashboard as _get_dashboard

	return _get_dashboard(from_date, to_date, user)


@frappe.whitelist()
def get_chart(
	name: str,
	type: str = "line",
	from_date: str | None = None,
	to_date: str | None = None,
	user: str | None = None,
):
	require_module("dashboard")
	from crm.api.dashboard import get_chart as _get_chart

	return _get_chart(name, type, from_date, to_date, user)


@frappe.whitelist()
def get_views(doctype: str):
	_crm(doctype)
	from crm.api.views import get_views as _get_views

	return _get_views(doctype)


@frappe.whitelist()
def get_activities(name: str):
	"""Timeline for a lead or a deal. Notes and tasks are included by CRM."""
	if frappe.db.exists("CRM Deal", name):
		require_module("deal")
	elif frappe.db.exists("CRM Lead", name):
		require_module("lead")
	else:
		frappe.throw(_("Lead or Deal {0} not found").format(name), frappe.DoesNotExistError)

	from crm.api.activities import get_activities as _get_activities

	return _get_activities(name)


@frappe.whitelist(methods=["POST"])
def convert_lead(
	lead: str,
	deal: str | dict | None = None,
	existing_contact: str | None = None,
	existing_organization: str | None = None,
	if_converted: str = "Create",
):
	require_module("lead")
	require_module("deal")
	from crm.fcrm.doctype.crm_lead.crm_lead import convert_to_deal

	return convert_to_deal(
		lead,
		deal=deal,
		existing_contact=existing_contact,
		existing_organization=existing_organization,
		if_converted=if_converted,
	)


@frappe.whitelist(methods=["POST"])
def add_deal_contact(deal: str, contact: str):
	require_module("deal")
	from crm.fcrm.doctype.crm_deal.crm_deal import add_contact

	return add_contact(deal, contact)


@frappe.whitelist(methods=["POST"])
def remove_deal_contact(deal: str, contact: str):
	require_module("deal")
	from crm.fcrm.doctype.crm_deal.crm_deal import remove_contact

	return remove_contact(deal, contact)


@frappe.whitelist(methods=["POST"])
def set_deal_primary_contact(deal: str, contact: str):
	require_module("deal")
	from crm.fcrm.doctype.crm_deal.crm_deal import set_primary_contact

	return set_primary_contact(deal, contact)


@frappe.whitelist(methods=["POST"])
def set_note_pinned(name: str, pinned: bool):
	require_module("notes")
	from crm.fcrm.doctype.fcrm_note.fcrm_note import set_pinned

	return set_pinned(name, pinned)


@frappe.whitelist(methods=["POST"])
def add_comment(reference_doctype: str, reference_name: str, content: str, attachments: list | str | None = None):
	_crm(reference_doctype)
	if isinstance(attachments, str):
		attachments = frappe.parse_json(attachments)
	from crm.api.comment import add_comment as _add_comment

	return _add_comment(reference_doctype, reference_name, content, attachments)


@frappe.whitelist(methods=["POST"])
def assign(doctype: str, name: str, assign_to: list | str, description: str | None = None):
	_crm(doctype)
	assignees = frappe.parse_json(assign_to) if isinstance(assign_to, str) else assign_to
	from frappe.desk.form.assign_to import _add

	return _add(
		{"assign_to": assignees, "doctype": doctype, "name": name, "description": description or ""},
		ignore_permissions=False,
		validate_assignees=True,
	)


@frappe.whitelist(methods=["POST"])
def unassign(doctype: str, name: str, assignees: list | str):
	_crm(doctype)
	from crm.api.doc import remove_assignments

	return remove_assignments(doctype, name, assignees)


@frappe.whitelist(methods=["POST"])
def set_as_primary_contact(contact: str, field: str, value: str):
	require_module("contact")
	from crm.api.contact import set_as_primary

	return set_as_primary(contact, field, value)


@frappe.whitelist(methods=["POST"])
def create_contact_detail(contact: str, field: str, value: str):
	require_module("contact")
	from crm.api.contact import create_new

	return create_new(contact, field, value)


@frappe.whitelist()
def get_attachments(doctype: str, name: str):
	_crm(doctype)
	from hrms.api import get_attachments as _get_attachments

	return _get_attachments(doctype, name)


@frappe.whitelist(methods=["POST"])
def upload_base64_file(content: str, filename: str, dt: str, dn: str, fieldname: str | None = None):
	_crm(dt)
	from hrms.api import upload_base64_file as _upload

	return _upload(content, filename, dt, dn, fieldname)


@frappe.whitelist(methods=["POST"])
def delete_attachment(filename: str):
	attached_to_doctype = frappe.db.get_value("File", filename, "attached_to_doctype")
	if attached_to_doctype:
		_crm(attached_to_doctype)
	else:
		require_access()
	from hrms.api import delete_attachment as _delete

	return _delete(filename)
