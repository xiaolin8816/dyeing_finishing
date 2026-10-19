import frappe


def execute():
	for name in frappe.get_all("Machine Production Calendar", pluck="name"):
		frappe.db.set_value("Machine Production Calendar", name, "maintenance_no", name, update_modified=False)
