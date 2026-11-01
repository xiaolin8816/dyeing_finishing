import json

import frappe


COST_TARGETS = {
	"Dyeing Cost Element",
	"Dyeing Cost Estimate",
	"Dyeing Cost Rate Standard",
	"Dyeing Production Actual",
	"Dyeing Energy Meter",
	"Dyeing Energy Meter Reading",
	"Dyeing Energy Allocation",
	"Dyeing Flow Card Cost Settlement",
}


def execute():
	if not frappe.db.exists("Workspace", "成本管理"):
		frappe.throw("成本管理工作区尚未创建")
	_remove_production_cost_card()
	_add_home_shortcut()
	frappe.cache.delete_key("bootinfo")


def _remove_production_cost_card():
	workspace = frappe.get_doc("Workspace", "生产管理")
	links = [
		row for row in workspace.links
		if not (row.type == "Card Break" and row.label == "成本管理")
		and row.link_to not in COST_TARGETS
	]
	content = json.loads(workspace.content or "[]")
	content = [
		block for block in content
		if block.get("id") not in ("生产管理-成本管理-header", "生产管理-成本管理-card")
	]
	if len(links) != len(workspace.links) or len(content) != len(json.loads(workspace.content or "[]")):
		workspace.set("links", links)
		workspace.content = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
		_save_workspace(workspace)


def _add_home_shortcut():
	workspace = frappe.get_doc("Workspace", "印染管理")
	shortcuts = list(workspace.shortcuts)
	content = json.loads(workspace.content or "[]")
	changed = False
	if not any(row.label == "成本管理" for row in shortcuts):
		index = next((i + 1 for i, row in enumerate(shortcuts) if row.label == "生产管理"), len(shortcuts))
		shortcuts.insert(index, {
			"color": "Grey", "doc_view": "", "label": "成本管理",
			"type": "URL", "url": "/desk/成本管理",
		})
		workspace.set("shortcuts", shortcuts)
		changed = True
	if not any(block.get("id") == "cost-management-shortcut" for block in content):
		index = next((i + 1 for i, block in enumerate(content) if block.get("id") == "production-management-shortcut"), len(content))
		content.insert(index, {
			"id": "cost-management-shortcut", "type": "shortcut",
			"data": {"shortcut_name": "成本管理", "col": 4},
		})
		workspace.content = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
		changed = True
	if changed:
		_save_workspace(workspace)


def _save_workspace(workspace):
	was_importing = frappe.flags.in_import
	frappe.flags.in_import = True
	try:
		workspace.save(ignore_permissions=True)
	finally:
		frappe.flags.in_import = was_importing
