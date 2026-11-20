"""Document reads and writes. Callers pass their own DocType allowlist.

Frappe document permissions still apply. This layer only adds the Sales Mobile
module switch and the field projection from Sales Mobile Settings.
"""

import frappe
from frappe.utils import cint

from sales_mobile.access import assert_writable, configured_fieldnames, parse_values, project, require_doctype
from sales_mobile.registry import ALWAYS_FIELDS

_SKIP_FIELDTYPES = {"Section Break", "Column Break", "Tab Break", "HTML", "Button", "Fold"}


def get_doc(doctype: str, name: str, allowed: dict):
	require_doctype(doctype, allowed)
	doc = frappe.get_doc(doctype, name)
	return project(doctype, "Detail", doc.as_dict())


def get_list(
	doctype: str,
	allowed: dict,
	filters=None,
	order_by: str = "modified desc",
	page_length: int = 20,
	start: int = 0,
):
	require_doctype(doctype, allowed)
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	configured = configured_fieldnames(doctype, "List")
	fields = ["*"] if not configured else list(dict.fromkeys(["name", *configured]))
	return frappe.get_list(
		doctype,
		filters=filters or {},
		fields=fields,
		order_by=order_by or "modified desc",
		limit_page_length=cint(page_length) or 20,
		limit_start=cint(start),
	)


def create_doc(doctype: str, values, allowed: dict):
	require_doctype(doctype, allowed)
	assert_writable(doctype)
	payload = parse_values(values)
	payload.pop("doctype", None)
	doc = frappe.get_doc({"doctype": doctype, **payload})
	doc.insert()
	return project(doctype, "Detail", doc.as_dict())


def update_doc(doctype: str, name: str, values, allowed: dict):
	require_doctype(doctype, allowed)
	assert_writable(doctype)
	payload = parse_values(values)
	for key in ("doctype", "name", "owner", "creation", "modified"):
		payload.pop(key, None)
	doc = frappe.get_doc(doctype, name)
	doc.update(payload)
	doc.save()
	return project(doctype, "Detail", doc.as_dict())


def delete_doc(doctype: str, name: str, allowed: dict):
	require_doctype(doctype, allowed)
	assert_writable(doctype)
	frappe.delete_doc(doctype, name)
	return {"doctype": doctype, "name": name, "deleted": True}


def submit_doc(doctype: str, name: str, allowed: dict):
	require_doctype(doctype, allowed)
	assert_writable(doctype)
	doc = frappe.get_doc(doctype, name)
	doc.submit()
	return project(doctype, "Detail", doc.as_dict())


def cancel_doc(doctype: str, name: str, allowed: dict):
	require_doctype(doctype, allowed)
	assert_writable(doctype)
	doc = frappe.get_doc(doctype, name)
	doc.cancel()
	return project(doctype, "Detail", doc.as_dict())


def form_fields(doctype: str, allowed: dict) -> list[dict]:
	require_doctype(doctype, allowed)
	meta = frappe.get_meta(doctype)
	draft = frappe.new_doc(doctype)
	issubmittable = 1 if meta.is_submittable else 0
	allowed_names = set(configured_fieldnames(doctype, "Detail"))
	rows = []
	for df in meta.fields:
		if df.fieldtype in _SKIP_FIELDTYPES:
			continue
		if allowed_names and df.fieldname not in allowed_names:
			continue
		row = {
			"fieldname": df.fieldname,
			"label": df.label,
			"fieldtype": df.fieldtype,
			"options": df.options,
			"reqd": df.reqd,
			"read_only": df.read_only,
			"issubmittable": issubmittable,
		}
		value = draft.get(df.fieldname)
		if value is not None and value != "":
			row["default"] = value
		rows.append(row)
	if allowed_names:
		for fieldname in ALWAYS_FIELDS & allowed_names:
			if not any(row["fieldname"] == fieldname for row in rows):
				row = {
					"fieldname": fieldname,
					"label": fieldname,
					"fieldtype": "Data",
					"reqd": 0,
					"issubmittable": issubmittable,
				}
				value = draft.get(fieldname)
				if value is not None and value != "":
					row["default"] = value
				rows.append(row)
	return rows


def doc_permissions(doctype: str, name: str, allowed: dict):
	require_doctype(doctype, allowed)
	from frappe.client import get_doc_permissions

	return get_doc_permissions(doctype, name)


def has_permission(doctype: str, name: str, perm_type: str, allowed: dict):
	require_doctype(doctype, allowed)
	return {"has_permission": bool(frappe.has_permission(doctype, perm_type, name))}
