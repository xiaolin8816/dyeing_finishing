import frappe


def execute():
	"""Recalculate production completion before applying downstream logistics progress."""
	from dyeing_finishing.dyeing_finishing.doctype.finished_product_customer_transfer.finished_product_customer_transfer import (
		refresh_customer_transfer_progress,
	)
	from dyeing_finishing.dyeing_finishing.doctype.finished_product_packing_receipt.finished_product_packing_receipt import (
		refresh_packing_progress_summary,
	)

	flow_cards = {
		row.production_flow_card
		for row in frappe.get_all(
			"Finished Product Packing Receipt",
			filters={"docstatus": 1},
			fields=["production_flow_card"],
		)
		if row.production_flow_card
	}
	for flow_card in flow_cards:
		refresh_packing_progress_summary(flow_card)
		refresh_customer_transfer_progress(flow_card)

