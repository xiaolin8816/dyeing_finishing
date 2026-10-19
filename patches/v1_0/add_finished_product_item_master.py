import json
from pathlib import Path

import frappe


def execute():
	if not frappe.db.exists("Item Group", "成品"):
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": "成品",
				"parent_item_group": "All Item Groups",
				"is_group": 0,
			}
		).insert(ignore_permissions=True)

	workspace_file = Path(
		frappe.get_app_path(
			"dyeing_finishing",
			"dyeing_finishing",
			"workspace",
			"成品管理",
			"成品管理.json",
		)
	)
	source = json.loads(workspace_file.read_text(encoding="utf-8"))
	workspace = frappe.get_doc("Workspace", "成品管理")
	workspace.content = source["content"]
	workspace.set("links", source.get("links", []))
	workspace.set("shortcuts", source.get("shortcuts", []))
	workspace.save(ignore_permissions=True)
	frappe.cache.delete_key("bootinfo")
