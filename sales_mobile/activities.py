"""One activity payload for every Sales Mobile document.

Leads and deals use the CRM timeline. Every other DocType uses the same
event types, built from the document's comments, versions, and linked notes.
"""

import json

import frappe
from frappe import _
from frappe.desk.form.load import get_docinfo
from frappe.utils import get_datetime

from sales_mobile.access import require_doctype


def document_activity(doctype: str, name: str, allowed: dict) -> dict:
	require_doctype(doctype, allowed)
	if not frappe.has_permission(doctype, "read", name):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} not found").format(doctype, name), frappe.DoesNotExistError)

	if doctype == "CRM Deal":
		return _from_crm("deal", name)
	if doctype == "CRM Lead":
		return _from_crm("lead", name)
	return _from_docinfo(doctype, name)


def _from_crm(kind: str, name: str) -> dict:
	from crm.api.activities import get_deal_activities, get_lead_activities

	activities, calls, notes, tasks, attachments = (
		get_deal_activities(name) if kind == "deal" else get_lead_activities(name)
	)
	return {
		"activities": activities,
		"calls": calls or [],
		"notes": notes or [],
		"tasks": tasks or [],
		"attachments": attachments or [],
	}


def _from_docinfo(doctype: str, name: str) -> dict:
	doc = frappe.get_doc(doctype, name)
	get_docinfo(doc)
	docinfo = frappe.response.pop("docinfo", frappe._dict())
	meta = frappe.get_meta(doctype)
	fields = {df.fieldname: df for df in meta.fields}
	label = (meta.get_title_field() and doc.get(meta.get_title_field())) or name
	activities = [
		{
			"activity_type": "creation",
			"creation": doc.creation,
			"owner": doc.owner,
			"data": _("created {0}").format(label),
		}
	]

	for version in reversed(docinfo.get("versions") or []):
		activities.extend(_version_activities(version, fields))

	for comment in docinfo.get("comments") or []:
		activities.append(
			{
				"name": comment.name,
				"activity_type": "comment",
				"creation": comment.creation,
				"owner": comment.owner,
				"content": comment.content,
			}
		)

	for row in (docinfo.get("communications") or []) + (docinfo.get("automated_messages") or []):
		activities.append(
			{
				"activity_type": "communication",
				"name": row.name,
				"communication_type": row.communication_type,
				"creation": row.communication_date or row.creation,
				"owner": row.owner,
				"data": {
					"subject": row.subject,
					"content": row.content,
					"sender": row.sender,
					"sender_full_name": row.sender_full_name,
					"recipients": row.recipients,
				},
			}
		)

	for row in docinfo.get("attachment_logs") or []:
		from crm.api.activities import parse_attachment_log

		activities.append(
			{
				"name": row.name,
				"activity_type": "attachment_log",
				"creation": row.creation,
				"owner": row.owner,
				"data": parse_attachment_log(row.content, row.comment_type),
			}
		)

	for row in docinfo.get("assignment_logs") or []:
		activities.append(
			{
				"name": row.name,
				"activity_type": "assignment",
				"creation": row.creation,
				"owner": row.owner,
				"content": row.content,
			}
		)

	for row in docinfo.get("workflow_logs") or []:
		activities.append(
			{
				"name": row.name,
				"activity_type": "workflow",
				"creation": row.creation,
				"owner": row.owner,
				"content": row.content,
			}
		)

	notes = _linked("FCRM Note", doctype, name, ["name", "title", "content", "owner", "creation", "pinned"])
	tasks = _linked(
		"CRM Task",
		doctype,
		name,
		["name", "title", "description", "status", "priority", "due_date", "assigned_to", "owner", "creation"],
	)
	for note in notes:
		activities.append(
			{
				"activity_type": "note",
				"name": note.name,
				"creation": note.creation,
				"owner": note.owner,
				"content": note.title or note.content,
			}
		)
	for task in tasks:
		activities.append(
			{
				"activity_type": "task",
				"name": task.name,
				"creation": task.creation,
				"owner": task.owner,
				"content": task.title,
				"data": {"status": task.status, "due_date": task.due_date},
			}
		)

	attachments = frappe.get_list(
		"File",
		filters={"attached_to_doctype": doctype, "attached_to_name": name},
		fields=["name", "file_name", "file_url", "is_private", "owner", "creation"],
		order_by="creation desc",
	)
	activities.sort(key=lambda row: get_datetime(row.get("creation")), reverse=True)
	return {
		"activities": activities,
		"calls": [],
		"notes": notes,
		"tasks": tasks,
		"attachments": attachments,
	}


def _version_activities(version, fields: dict) -> list[dict]:
	try:
		payload = json.loads(version.data or "{}")
	except (TypeError, ValueError):
		return []
	rows = []
	for change in payload.get("changed") or []:
		if not change or len(change) < 3:
			continue
		fieldname, old, new = change[0], change[1], change[2]
		df = fields.get(fieldname)
		if not df or df.fieldtype in {"Section Break", "Column Break", "Tab Break"}:
			continue
		if not old and not new:
			continue
		data = {"field": fieldname, "field_label": df.label or fieldname, "old_value": old, "value": new}
		activity_type = "changed"
		if not old and new:
			activity_type = "added"
			data = {"field": fieldname, "field_label": df.label or fieldname, "value": new}
		elif old and not new:
			activity_type = "removed"
			data = {"field": fieldname, "field_label": df.label or fieldname, "value": old}
		rows.append(
			{
				"activity_type": activity_type,
				"creation": version.creation,
				"owner": version.owner,
				"data": data,
			}
		)
	return rows


def _linked(doctype: str, reference_doctype: str, reference_name: str, fields: list[str]) -> list:
	if not frappe.db.exists("DocType", doctype) or not frappe.has_permission(doctype, "read"):
		return []
	return frappe.get_list(
		doctype,
		filters={"reference_doctype": reference_doctype, "reference_docname": reference_name},
		fields=fields,
		order_by="creation desc",
	)
