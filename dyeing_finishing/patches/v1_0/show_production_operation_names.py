import frappe


def execute():
	operations = {
		row.name: row.production_operation_name
		for row in frappe.get_all(
			"Production Operation", fields=["name", "production_operation_name"]
		)
	}
	for operation, operation_name in operations.items():
		frappe.db.sql(
			"""UPDATE `tabProduction Flow Card Progress`
			SET operation=%s WHERE operation=%s""",
			(operation_name, operation),
		)

