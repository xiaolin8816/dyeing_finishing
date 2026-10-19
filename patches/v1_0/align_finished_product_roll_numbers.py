import frappe


def execute():
	flow_cards = set(filter(None, frappe.get_all(
		"Finished Product Packing Receipt", pluck="production_flow_card"
	)))
	for flow_card in flow_cards:
		prefix = "FP" + "".join(character for character in flow_card if character.isalnum())
		cancelled = frappe.db.sql(
			"""SELECT item.name
			FROM `tabFinished Product Packing Receipt Item` item
			INNER JOIN `tabFinished Product Packing Receipt` parent ON parent.name = item.parent
			WHERE parent.production_flow_card = %s AND parent.docstatus = 2""",
			flow_card, as_dict=True,
		)
		for row in cancelled:
			value = f"CANCELLED-{row.name}"
			frappe.db.set_value("Finished Product Packing Receipt Item", row.name, {"roll_no": value, "barcode": value}, update_modified=False)

		rows = frappe.db.sql(
			"""SELECT item.name
			FROM `tabFinished Product Packing Receipt Item` item
			INNER JOIN `tabFinished Product Packing Receipt` parent ON parent.name = item.parent
			WHERE parent.production_flow_card = %s AND parent.docstatus < 2
			ORDER BY parent.packing_date, parent.creation, parent.name, item.idx""",
			flow_card, as_dict=True,
		)
		# Move every active row aside first so the unique roll_no constraint cannot
		# conflict while consecutive numbers are shifted down.
		for row in rows:
			value = f"REN-{row.name}"
			frappe.db.set_value("Finished Product Packing Receipt Item", row.name, {"roll_no": value, "barcode": value}, update_modified=False)
		for piece_no, row in enumerate(rows, 1):
			roll_no = f"{prefix}-{piece_no:03d}"
			frappe.db.set_value(
				"Finished Product Packing Receipt Item", row.name,
				{"piece_no": piece_no, "roll_no": roll_no, "barcode": roll_no},
				update_modified=False,
			)
