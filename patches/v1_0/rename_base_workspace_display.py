import frappe


WORKSPACE = "印染基础资料"
DISPLAY_NAME = "基础资料"


def execute():
	if frappe.db.exists("Workspace", WORKSPACE):
		content = frappe.db.get_value("Workspace", WORKSPACE, "content") or ""
		frappe.db.set_value("Workspace", WORKSPACE, {
			"label": DISPLAY_NAME,
			"title": DISPLAY_NAME,
			"content": content.replace("印染基础资料", DISPLAY_NAME),
		}, update_modified=False)

	if frappe.db.exists("Workspace", "印染整理"):
		content = frappe.db.get_value("Workspace", "印染整理", "content") or ""
		frappe.db.set_value("Workspace", "印染整理", "content",
			content.replace("印染基础资料", DISPLAY_NAME), update_modified=False)
		frappe.db.sql("""UPDATE `tabWorkspace Shortcut` SET label=%s
			WHERE parent='印染整理' AND url='/desk/印染基础资料'""", DISPLAY_NAME)
		if not frappe.db.exists("Workspace Shortcut", {
			"parent": "印染整理",
			"url": "/desk/系统管理",
		}):
			shortcut = frappe.new_doc("Workspace Shortcut")
			shortcut.update({
				"parent": "印染整理",
				"parenttype": "Workspace",
				"parentfield": "shortcuts",
				"idx": frappe.db.count("Workspace Shortcut", {"parent": "印染整理"}) + 1,
				"label": "系统管理",
				"type": "URL",
				"url": "/desk/系统管理",
				"color": "Grey",
			})
			shortcut.db_insert()

	if frappe.db.exists("Workspace Sidebar", "印染整理"):
		frappe.db.sql("""UPDATE `tabWorkspace Sidebar Item` SET label=%s
			WHERE parent='印染整理' AND link_to=%s""", (DISPLAY_NAME, WORKSPACE))

	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")
