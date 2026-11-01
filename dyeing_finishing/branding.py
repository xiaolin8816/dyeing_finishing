"""Keep the public product branding separate from stable APP identifiers."""

import json
import frappe
from frappe.model.rename_doc import rename_doc


OLD_WORKSPACE = "印染整理"
WORKSPACE_NAME = "印染管理"
WORKSPACE_LABEL = "印染管理"
OLD_SIDEBAR = "印染整理"
SIDEBAR_NAME = "印染管理"
DESKTOP_ICON_NAME = "印染整理"


def sync_public_branding():
	"""Apply user-facing names after every migration without changing APP identifiers."""
	_sync_workspace()
	_sync_sidebar()
	_sync_desktop_icon()
	frappe.clear_cache()


def _sync_workspace():
	if frappe.db.exists("Workspace", OLD_WORKSPACE) and not frappe.db.exists("Workspace", WORKSPACE_NAME):
		old_workspace = frappe.get_doc("Workspace", OLD_WORKSPACE)
		old_workspace.content = (old_workspace.content or "").replace("印染整理", WORKSPACE_LABEL)
		old_workspace.save(ignore_permissions=True)
		rename_doc(
			"Workspace", OLD_WORKSPACE, WORKSPACE_NAME, force=True,
			ignore_permissions=True, show_alert=False,
		)
	if not frappe.db.exists("Workspace", WORKSPACE_NAME):
		return
	workspace = frappe.get_doc("Workspace", WORKSPACE_NAME)
	workspace.label = WORKSPACE_LABEL
	workspace.title = WORKSPACE_LABEL
	workspace.content = _workspace_content(workspace.content)
	workspace.save(ignore_permissions=True)
	frappe.db.set_value("Workspace", WORKSPACE_NAME, {"label": WORKSPACE_LABEL, "title": WORKSPACE_LABEL}, update_modified=False)
	frappe.db.sql("UPDATE `tabWorkspace` SET parent_page=%s WHERE parent_page=%s", (WORKSPACE_NAME, OLD_WORKSPACE))


def _workspace_content(content):
	blocks = json.loads((content or "[]").replace("印染整理", WORKSPACE_LABEL))
	if not any(block.get("id") == "system-management-shortcut" for block in blocks):
		blocks.append({
			"id": "system-management-shortcut",
			"type": "shortcut",
			"data": {"shortcut_name": "系统管理", "col": 4},
		})
	return json.dumps(blocks, ensure_ascii=False, separators=(",", ":"))


def _sync_sidebar():
	old_exists = frappe.db.exists("Workspace Sidebar", OLD_SIDEBAR)
	new_exists = frappe.db.exists("Workspace Sidebar", SIDEBAR_NAME)
	if old_exists and not new_exists:
		rename_doc(
			"Workspace Sidebar",
			OLD_SIDEBAR,
			SIDEBAR_NAME,
			force=True,
			ignore_permissions=True,
			show_alert=False,
		)
	elif old_exists and new_exists:
		frappe.delete_doc("Workspace Sidebar", OLD_SIDEBAR, ignore_permissions=True, force=True)
	if not frappe.db.exists("Workspace Sidebar", SIDEBAR_NAME):
		return
	sidebar = frappe.get_doc("Workspace Sidebar", SIDEBAR_NAME)
	sidebar.title = SIDEBAR_NAME
	for item in sidebar.items:
		if item.link_type == "Workspace" and item.link_to in (OLD_WORKSPACE, WORKSPACE_NAME) and not item.child:
			item.label = f"{WORKSPACE_LABEL}首页"
			item.link_to = WORKSPACE_NAME
	sidebar.save(ignore_permissions=True)


def _sync_desktop_icon():
	if not frappe.db.exists("Desktop Icon", DESKTOP_ICON_NAME):
		return
	frappe.db.set_value(
		"Desktop Icon",
		DESKTOP_ICON_NAME,
		{"label": WORKSPACE_LABEL, "link_to": SIDEBAR_NAME, "sidebar": SIDEBAR_NAME},
		update_modified=False,
	)
