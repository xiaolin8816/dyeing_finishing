import json
from pathlib import Path

import frappe


def execute():
	if not frappe.db.exists("UOM", "Y"):
		frappe.get_doc({"doctype": "UOM", "uom_name": "Y", "must_be_whole_number": 0}).insert(ignore_permissions=True)

	if not frappe.db.exists("Warehouse", "成品仓库 - 沅泰"):
		company = frappe.db.get_value("Warehouse", "生产中转仓 - 沅泰", "company")
		if company:
			frappe.get_doc(
				{
					"doctype": "Warehouse",
					"warehouse_name": "成品仓库",
					"company": company,
					"is_group": 0,
				}
			).insert(ignore_permissions=True)

	workspace_file = Path(
		frappe.get_app_path(
			"dyeing_finishing", "dyeing_finishing", "workspace", "成品管理", "成品管理.json"
		)
	)
	source = json.loads(workspace_file.read_text(encoding="utf-8"))
	workspace = frappe.get_doc("Workspace", "成品管理")
	workspace.content = source["content"]
	workspace.set("links", source.get("links", []))
	workspace.set("shortcuts", source.get("shortcuts", []))
	workspace.save(ignore_permissions=True)
	frappe.cache.delete_key("bootinfo")
