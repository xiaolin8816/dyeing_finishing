import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Stock Entry Detail": [
				{
					"fieldname": "custom_yard_qty",
					"label": "码数",
					"fieldtype": "Float",
					"precision": 3,
					"insert_after": "custom_roll_count",
					"read_only": 1,
					"in_list_view": 1,
				},
				{
					"fieldname": "custom_yard_uom",
					"label": "码数单位",
					"fieldtype": "Link",
					"options": "UOM",
					"insert_after": "custom_yard_qty",
					"read_only": 1,
				},
			],
		},
		update=True,
	)

	for receipt in frappe.get_all(
		"Finished Product Packing Receipt",
		filters={"docstatus": 1, "stock_entry": ["is", "set"]},
		fields=["name", "stock_entry", "finished_item_code", "total_roll_count", "total_yard_qty"],
	):
		frappe.db.set_value(
			"Stock Entry Detail",
			{
				"parent": receipt.stock_entry,
				"item_code": receipt.finished_item_code,
				"custom_finished_packing_receipt": receipt.name,
			},
			{
				"custom_roll_count": receipt.total_roll_count,
				"custom_yard_qty": receipt.total_yard_qty,
				"custom_yard_uom": "Y",
			},
			update_modified=False,
		)
