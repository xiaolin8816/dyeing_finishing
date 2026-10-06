import json
from pathlib import Path

import frappe

from dyeing_finishing.patches.v1_0.consolidate_dyeing_workspace_sidebar import (
	execute as sync_sidebar,
)


WORKSPACE = "印染基础资料"


def execute():
	"""在印染基础资料中增加 ERPNext 标准物料组入口。"""
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
	workspace.save(ignore_permissions=True)
	sync_sidebar()
	frappe.cache.delete_key("bootinfo")
