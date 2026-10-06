import json
from pathlib import Path

import frappe


WORKSPACE = "印染整理"


def execute():
	"""在旧升级任务执行后，以应用内的最终定义统一印染整理首页。"""
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
	for fieldname in ("links", "shortcuts", "charts", "number_cards", "quick_lists", "custom_blocks"):
		workspace.set(fieldname, source.get(fieldname, []))

	workspace.save(ignore_permissions=True)
	frappe.cache.delete_key("bootinfo")
