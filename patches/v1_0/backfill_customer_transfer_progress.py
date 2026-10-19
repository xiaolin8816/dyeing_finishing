import frappe


def execute():
	from dyeing_finishing.dyeing_finishing.doctype.finished_product_customer_transfer.finished_product_customer_transfer import (
		refresh_customer_transfer_progress,
	)

	flow_cards = set()
	for name, flow_card in frappe.get_all(
		"Finished Product Customer Transfer",
		filters={"docstatus": 1},
		fields=["name", "production_flow_card"],
		as_list=True,
	):
		flow_cards.add(flow_card)
		if frappe.db.exists("Production Flow Card Progress", {
			"parent": flow_card,
			"source_doctype": "Finished Product Customer Transfer",
			"source_document": name,
		}):
			continue
		frappe.get_doc("Finished Product Customer Transfer", name)._record_progress()

	for flow_card in flow_cards:
		refresh_customer_transfer_progress(flow_card)
