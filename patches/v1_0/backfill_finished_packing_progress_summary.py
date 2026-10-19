import frappe


def execute():
	from dyeing_finishing.dyeing_finishing.doctype.finished_product_packing_receipt.finished_product_packing_receipt import (
		refresh_packing_progress_summary,
	)

	flow_cards = frappe.get_all(
		"Finished Product Packing Receipt",
		filters={"production_flow_card": ["is", "set"]},
		pluck="production_flow_card",
		distinct=True,
	)
	for flow_card in flow_cards:
		refresh_packing_progress_summary(flow_card)

	for receipt in frappe.get_all(
		"Finished Product Packing Receipt",
		fields=["name", "total_roll_count", "total_yard_qty"],
	):
		frappe.db.set_value(
			"Production Flow Card Progress",
			{
				"source_doctype": "Finished Product Packing Receipt",
				"source_document": receipt.name,
			},
			{
				"roll_count": receipt.total_roll_count,
				"yard_qty": receipt.total_yard_qty,
			},
			update_modified=False,
		)
