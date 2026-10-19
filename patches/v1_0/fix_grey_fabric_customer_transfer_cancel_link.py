import frappe


def execute():
	for dt in ("Stock Entry", "Stock Entry Detail"):
		name = frappe.db.get_value("Custom Field", {"dt":dt, "fieldname":"custom_grey_fabric_customer_transfer"})
		if name:
			frappe.db.set_value("Custom Field", name, {"fieldtype":"Data", "options":None, "label":"胚布过户单号"}, update_modified=False)
			frappe.clear_cache(doctype=dt)
