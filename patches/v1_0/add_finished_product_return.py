import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields({
		"Stock Entry": [{
			"fieldname": "custom_finished_product_return",
			"label": "成品退货处理单",
			"fieldtype": "Link",
			"options": "Finished Product Return",
			"insert_after": "custom_finished_product_delivery",
			"read_only": 1,
			"no_copy": 1,
		}],
		"Stock Entry Detail": [{
			"fieldname": "custom_finished_product_return",
			"label": "成品退货处理单",
			"fieldtype": "Link",
			"options": "Finished Product Return",
			"insert_after": "custom_finished_product_delivery",
			"read_only": 1,
			"no_copy": 1,
		}],
	}, update=True)

	company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
	if not company:
		return
	abbr = frappe.db.get_value("Company", company, "abbr")
	warehouse = f"成品退货待检仓 - {abbr}"
	if not frappe.db.exists("Warehouse", warehouse):
		frappe.get_doc({
			"doctype": "Warehouse",
			"warehouse_name": "成品退货待检仓",
			"company": company,
			"is_group": 0,
		}).insert(ignore_permissions=True)
	frappe.db.set_single_value("Dyeing System Settings", "finished_product_return_warehouse", warehouse)
