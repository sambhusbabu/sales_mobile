import frappe
from frappe import _
from frappe.model.document import Document

from sales_mobile.access import known_doctype, validate_color
from sales_mobile.registry import ALWAYS_FIELDS, MODULES


class SalesMobileSettings(Document):
	def validate(self):
		validate_color(self.primary_color, _("Primary Color"))
		validate_color(self.accent_color, _("Accent Color"))
		self.validate_tabs()
		self.validate_fields()

	def validate_tabs(self):
		seen = set()
		for row in self.tabs or []:
			if row.module not in MODULES:
				frappe.throw(_("Row {0}: module {1} is not a Sales Mobile module").format(row.idx, row.module))
			if row.tab_key in seen:
				frappe.throw(_("Tab key {0} is used more than once").format(row.tab_key))
			seen.add(row.tab_key)

	def validate_fields(self):
		for row in self.fields or []:
			if not known_doctype(row.reference_doctype):
				frappe.throw(
					_("Row {0}: {1} is not a Sales Mobile DocType").format(row.idx, row.reference_doctype)
				)
			if row.view not in ("List", "Detail"):
				frappe.throw(_("Row {0}: view must be List or Detail").format(row.idx))
			if not frappe.db.exists("DocType", row.reference_doctype):
				continue
			meta = frappe.get_meta(row.reference_doctype)
			if (
				row.fieldname not in ALWAYS_FIELDS
				and not row.fieldname.startswith("_")
				and not meta.get_field(row.fieldname)
			):
				frappe.throw(
					_("Field {0} does not exist on {1}").format(row.fieldname, row.reference_doctype)
				)
