import json
from pathlib import Path

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Stock Entry": [{
				"fieldname": "custom_finished_product_delivery",
				"label": "成品出库单",
				"fieldtype": "Link",
				"options": "Finished Product Delivery",
				"insert_after": "custom_finished_packing_receipt",
				"read_only": 1,
				"module": "dyeing_finishing",
			}],
			"Stock Entry Detail": [{
				"fieldname": "custom_finished_product_delivery",
				"label": "成品出库单",
				"fieldtype": "Link",
				"options": "Finished Product Delivery",
				"insert_after": "custom_finished_packing_receipt",
				"read_only": 1,
				"module": "dyeing_finishing",
			}],
		},
		update=True,
	)

	workspace_file = Path(
		frappe.get_app_path("dyeing_finishing", "dyeing_finishing", "workspace", "成品管理", "成品管理.json")
	)
	source = json.loads(workspace_file.read_text(encoding="utf-8"))
	workspace = frappe.get_doc("Workspace", "成品管理")
	workspace.content = source["content"]
	workspace.set("links", source.get("links", []))
	workspace.set("shortcuts", source.get("shortcuts", []))
	workspace.save(ignore_permissions=True)
	frappe.cache.delete_key("bootinfo")
