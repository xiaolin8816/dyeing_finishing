import frappe


def execute():
	if not frappe.db.exists("DocType", "Finished Product Delivery"):
		return
	default_company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	for row in frappe.get_all(
		"Finished Product Delivery",
		filters=[["company", "is", "not set"]],
		fields=["name", "production_flow_card"],
	):
		company = frappe.db.get_value("Production Flow Card", row.production_flow_card, "company") if row.production_flow_card else None
		frappe.db.set_value("Finished Product Delivery", row.name, "company", company or default_company, update_modified=False)
