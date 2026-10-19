import frappe


def execute():
	flow_cards = frappe.get_all(
		"Finished Product Packing Receipt",
		filters={"docstatus": ["<", 2]},
		pluck="production_flow_card",
		distinct=True,
	)
	for flow_card in filter(None, flow_cards):
		rows = frappe.db.sql(
			"""SELECT item.name
			FROM `tabFinished Product Packing Receipt Item` item
			INNER JOIN `tabFinished Product Packing Receipt` parent ON parent.name = item.parent
			WHERE parent.production_flow_card = %s AND parent.docstatus < 2
			ORDER BY parent.packing_date, parent.creation, parent.name, item.idx""",
			flow_card,
			as_dict=True,
		)
		for piece_no, row in enumerate(rows, 1):
			frappe.db.set_value(
				"Finished Product Packing Receipt Item", row.name,
				"piece_no", piece_no, update_modified=False,
			)
