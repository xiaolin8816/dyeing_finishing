import frappe


CHILD_WORKSPACES = (
	"印染基础资料",
	"配方与工艺",
	"胚布管理",
	"生产管理",
	"染料管理",
	"成品管理",
)


def execute():
	"""删除 Frappe 为子工作区自动生成的桌面入口。"""
	for workspace in CHILD_WORKSPACES:
		frappe.delete_doc_if_exists("Desktop Icon", workspace, force=True)

	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")
