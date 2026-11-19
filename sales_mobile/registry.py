"""DocTypes and modules the mobile app is allowed to route to.

These maps are the allowlist. A request for any other DocType is rejected.
"""

# module key -> settings checkbox fieldname
MODULES = {
	"dashboard": "enable_dashboard",
	"lead": "enable_lead",
	"deal": "enable_deal",
	"contact": "enable_contact",
	"organization": "enable_organization",
	"notes": "enable_notes",
	"tasks": "enable_tasks",
	"hrms_home": "enable_hrms_home",
	"attendance": "enable_attendance",
	"leave": "enable_leave",
	"expense_claim": "enable_expense_claim",
	"employee_advance": "enable_employee_advance",
	"salary_slip": "enable_salary_slip",
	"profile": "enable_profile",
	"notifications": "enable_notifications",
}

# DocType -> module key
CRM_DOCTYPES = {
	"CRM Lead": "lead",
	"CRM Deal": "deal",
	"Contact": "contact",
	"CRM Organization": "organization",
	"FCRM Note": "notes",
	"CRM Task": "tasks",
}

HRMS_DOCTYPES = {
	"Employee Checkin": "attendance",
	"Attendance Request": "attendance",
	"Shift Request": "attendance",
	"Shift Assignment": "attendance",
	"Leave Application": "leave",
	"Compensatory Leave Request": "leave",
	"Expense Claim": "expense_claim",
	"Employee Advance": "employee_advance",
	"Salary Slip": "salary_slip",
	"PWA Notification": "notifications",
	"Employee": "profile",
}

DOCTYPES = {**CRM_DOCTYPES, **HRMS_DOCTYPES}

# Created by the desk or payroll. The mobile app can read them, not write them.
READ_ONLY = {"Salary Slip", "Employee"}

# Employees can mark their own notification read. Nothing else on this DocType.
NOTIFICATION_FIELDS = {"read"}

# Kept on every projected payload so the app can still identify the row.
ALWAYS_FIELDS = {"name", "doctype", "owner", "modified", "creation", "docstatus", "modified_by"}

DEFAULT_TABS = [
	{"tab_key": "dashboard", "label": "Dashboard", "module": "dashboard", "icon": "layout-dashboard", "show_on_home": 0},
	{"tab_key": "leads", "label": "Leads", "module": "lead", "icon": "user-plus", "show_on_home": 1},
	{"tab_key": "deals", "label": "Deals", "module": "deal", "icon": "briefcase", "show_on_home": 1},
	{"tab_key": "contacts", "label": "Contacts", "module": "contact", "icon": "contact", "show_on_home": 1},
	{"tab_key": "organizations", "label": "Organizations", "module": "organization", "icon": "building", "show_on_home": 1},
	{"tab_key": "notes", "label": "Notes", "module": "notes", "icon": "file-text", "show_on_home": 0},
	{"tab_key": "tasks", "label": "Tasks", "module": "tasks", "icon": "check-square", "show_on_home": 0},
	{"tab_key": "home", "label": "Home", "module": "hrms_home", "icon": "home", "show_on_home": 0},
	{"tab_key": "attendance", "label": "Attendance", "module": "attendance", "icon": "clock", "show_on_home": 1},
	{"tab_key": "leave", "label": "Leave", "module": "leave", "icon": "calendar", "show_on_home": 1},
	{"tab_key": "expenses", "label": "Expenses", "module": "expense_claim", "icon": "receipt", "show_on_home": 1},
	{"tab_key": "advances", "label": "Advances", "module": "employee_advance", "icon": "wallet", "show_on_home": 1},
	{"tab_key": "salary", "label": "Salary", "module": "salary_slip", "icon": "banknote", "show_on_home": 1},
	{"tab_key": "profile", "label": "Profile", "module": "profile", "icon": "user", "show_on_home": 0},
	{"tab_key": "notifications", "label": "Notifications", "module": "notifications", "icon": "bell", "show_on_home": 0},
]
