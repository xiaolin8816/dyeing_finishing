from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields({
		"Stock Entry": [{
			"fieldname": "custom_finished_product_customer_transfer",
			"label": "成品转客户单",
			"fieldtype": "Link",
			"options": "Finished Product Customer Transfer",
			"insert_after": "custom_finished_product_delivery",
			"read_only": 1,
			"no_copy": 1,
		}],
		"Stock Entry Detail": [{
			"fieldname": "custom_finished_product_customer_transfer",
			"label": "成品转客户单",
			"fieldtype": "Link",
			"options": "Finished Product Customer Transfer",
			"insert_after": "custom_finished_product_delivery",
			"read_only": 1,
			"no_copy": 1,
		}],
	}, update=True)
