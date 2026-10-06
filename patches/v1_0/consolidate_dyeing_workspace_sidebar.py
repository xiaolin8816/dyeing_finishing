import frappe

from dyeing_finishing.patches.v1_0.configure_dyeing_workspace_sidebar import ITEMS


SIDEBAR = "印染整理"
LEGACY_SIDEBAR = "dyeing_finishing"
GENERATED_CHILD_SIDEBARS = (
	"印染基础资料",
	"配方与工艺",
	"胚布管理",
	"生产管理",
	"染料管理",
	"成品管理",
)


def execute():
	"""只保留一套“印染整理”侧栏，避免子工作区选中自动侧栏。"""
	if frappe.db.exists("Workspace Sidebar", SIDEBAR):
		sidebar = frappe.get_doc("Workspace Sidebar", SIDEBAR)
	else:
		sidebar = frappe.new_doc("Workspace Sidebar")
		sidebar.title = SIDEBAR

	sidebar.app = "dyeing_finishing"
	sidebar.standard = 1
	sidebar.header_icon = "dye"
	sidebar.set("items", ITEMS)
	was_importing = frappe.flags.in_import
	frappe.flags.in_import = True
	try:
		if sidebar.is_new():
			sidebar.insert(ignore_permissions=True)
		else:
			sidebar.save(ignore_permissions=True)
	finally:
		frappe.flags.in_import = was_importing

	for name in (*GENERATED_CHILD_SIDEBARS, LEGACY_SIDEBAR):
		frappe.delete_doc_if_exists("Workspace Sidebar", name, force=True)

	if frappe.db.exists("Desktop Icon", SIDEBAR):
		frappe.db.set_value(
			"Desktop Icon",
			SIDEBAR,
			{"link_type": "Workspace Sidebar", "link_to": SIDEBAR, "sidebar": SIDEBAR},
			update_modified=False,
		)

	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")
