import frappe


def execute():
	parents = frappe.get_all("Production Flow Card Operation", pluck="parent", distinct=True)
	for parent in parents:
		rows = frappe.get_all(
			"Production Flow Card Operation",
			filters={"parent": parent},
			fields=["name", "sequence_no", "idx"],
			order_by="sequence_no asc, idx asc",
		)
		for index, row in enumerate(rows, 1):
			if row.idx != index:
				frappe.db.set_value("Production Flow Card Operation", row.name, "idx", index, update_modified=False)
