import frappe


def execute():
	rows = frappe.get_all("Finished Product Return to Grey Fabric", fields=["name", "production_flow_card"])
	for row in rows:
		source = frappe.db.get_value("Finished Product Return", {"production_flow_card": row.production_flow_card, "docstatus": 1}, ["customer", "customer_name"], as_dict=True)
		if source:
			frappe.db.set_value("Finished Product Return to Grey Fabric", row.name, {"customer": source.customer, "customer_name": source.customer_name}, update_modified=False)
