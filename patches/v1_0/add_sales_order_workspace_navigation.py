import json
from pathlib import Path

import frappe


WORKSPACE = "生产管理"


def execute():
	"""在生产管理中增加染整销售订单入口。"""
	workspace_file = Path(
		frappe.get_app_path(
			"dyeing_finishing",
			"dyeing_finishing",
			"workspace",
			WORKSPACE,
			f"{WORKSPACE}.json",
		)
	)
	source = json.loads(workspace_file.read_text(encoding="utf-8"))
	workspace = frappe.get_doc("Workspace", WORKSPACE)
	workspace.content = source["content"]
	workspace.set("links", source.get("links", []))
	workspace.set("shortcuts", source.get("shortcuts", []))
	workspace.save(ignore_permissions=True)
	frappe.cache.delete_key("bootinfo")
