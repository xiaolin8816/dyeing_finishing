import json
from pathlib import Path

import frappe
from frappe.desk.doctype.list_view_settings.list_view_settings import set_listview_fields


DOCTYPE = "Outsourcing Processing Order"
LIST_FIELDS = [
	{"label": "编号", "fieldname": "name"},
	{"label": "状态", "fieldname": "outsourcing_status"},
	{"label": "单据日期", "fieldname": "order_date"},
	{"label": "生产流转卡", "fieldname": "production_flow_card"},
	{"label": "客户名称", "fieldname": "customer_name"},
	{"label": "委外工序", "fieldname": "operation_name"},
	{"label": "加工商", "fieldname": "processing_contractor_name"},
	{"label": "计划匹数", "fieldname": "planned_roll_count"},
	{"label": "计划重量", "fieldname": "planned_weight"},
	{"label": "完工去向", "fieldname": "completion_destination"},
	{"label": "预计加工费", "fieldname": "estimated_processing_fee"},
	{"label": "预计交期", "fieldname": "planned_completion_date"},
]
LIST_LAYOUT = {
	"widths": {"name": 155, "outsourcing_status": 90, "order_date": 105, "production_flow_card": 145,
		"customer_name": 140, "operation_name": 110, "processing_contractor_name": 150, "planned_roll_count": 90,
		"planned_weight": 100, "completion_destination": 130, "estimated_processing_fee": 110,
		"planned_completion_date": 105},
	"order": [field["fieldname"] for field in LIST_FIELDS],
	"hidden": [],
	"sticky": ["name", "outsourcing_status", "production_flow_card"],
}


def execute():
	if not frappe.db.exists("DocType", DOCTYPE):
		frappe.throw("Outsourcing Processing Order DocType is missing")
	_configure_list()
	_sync_workspace("委外管理")
	_sync_root_workspace()
	_ensure_visual_print_template()
	from dyeing_finishing.patches.v1_0.consolidate_dyeing_workspace_sidebar import execute as sync_sidebar
	from dyeing_finishing.patches.v1_0.delete_child_workspace_desktop_icons import execute as hide_child_icons
	from dyeing_finishing.dyeing_finishing.branding import sync_public_branding
	_sync_sidebar_source()
	sync_sidebar()
	hide_child_icons()
	sync_public_branding()


def _configure_list():
	settings = frappe.get_doc("List View Settings", DOCTYPE) if frappe.db.exists("List View Settings", DOCTYPE) else frappe.new_doc("List View Settings")
	settings.name = DOCTYPE
	settings.fields = json.dumps(LIST_FIELDS, ensure_ascii=False)
	settings.disable_scrolling = 0
	settings.save(ignore_permissions=True)
	visible = {field["fieldname"] for field in LIST_FIELDS}
	current = [field.fieldname for field in frappe.get_meta(DOCTYPE).fields if field.in_list_view]
	set_listview_fields(DOCTYPE, LIST_FIELDS, [field for field in current if field not in visible])
	frappe.db.set_global("outsourcing_processing_order_list_layout", frappe.as_json(LIST_LAYOUT))
	frappe.clear_cache(doctype=DOCTYPE)


def _workspace_source(name):
	path = Path(frappe.get_app_path("dyeing_finishing", "dyeing_finishing", "workspace", name, f"{name}.json"))
	return json.loads(path.read_text(encoding="utf-8"))


def _sync_workspace(name):
	source = _workspace_source(name)
	workspace = frappe.get_doc("Workspace", name) if frappe.db.exists("Workspace", name) else frappe.new_doc("Workspace")
	for fieldname in ("name", "label", "title", "module", "app", "icon", "parent_page", "public", "sequence_id", "content"):
		if fieldname in source:
			setattr(workspace, fieldname, source[fieldname])
	for fieldname in ("links", "shortcuts", "charts", "number_cards", "quick_lists", "custom_blocks", "roles"):
		workspace.set(fieldname, source.get(fieldname, []))
	was_importing = frappe.flags.in_import
	frappe.flags.in_import = True
	try:
		workspace.insert(ignore_permissions=True) if workspace.is_new() else workspace.save(ignore_permissions=True)
	finally:
		frappe.flags.in_import = was_importing


def _sync_root_workspace():
	_sync_workspace("印染管理")


def _sync_sidebar_source():
	from dyeing_finishing.patches.v1_0.configure_dyeing_workspace_sidebar import ITEMS
	if frappe.db.exists("Workspace Sidebar", "印染管理"):
		sidebar = frappe.get_doc("Workspace Sidebar", "印染管理")
		sidebar.set("items", ITEMS)
		sidebar.save(ignore_permissions=True)


def _ensure_visual_print_template():
	if not frappe.db.exists("DocType", "Visual Print Template"):
		return
	from visual_print.bindings import ensure_template_binding
	from visual_print.visual_print_studio.page.visual_print_template_manager.visual_print_template_manager import (
		_default_visual_source_layout, _print_presentation, _visual_from_template_layout, save_visual_designer,
	)
	template_name = "委外加工单"
	if not frappe.db.exists("Visual Print Template", template_name):
		layout = _default_visual_source_layout(DOCTYPE, template_name)
		template = frappe.get_doc({"doctype": "Visual Print Template", "template_name": template_name,
			"doc_type": DOCTYPE, "module": frappe.get_meta(DOCTYPE).module, "purpose": "委外加工计划与审核",
			"display_order": 0, "applicable_docstatus": "全部",
			"allowed_roles": "Manufacturing Manager\nPurchase Manager\nStock Manager\nSystem Manager",
			"enabled": 1, "is_default": 1, "status": "Draft", "renderer": "Typst", "schema_version": 5,
			"pdf_standard": "PDF 1.7", "layout_json": json.dumps(layout, ensure_ascii=False),
			"presentation_settings": json.dumps(_print_presentation("A4"), ensure_ascii=False)})
		template.insert(ignore_permissions=True)
		visual = _visual_from_template_layout(template, layout)
		save_visual_designer(template.name, json.dumps(visual, ensure_ascii=False))
	template = frappe.get_doc("Visual Print Template", template_name)
	binding_name = ensure_template_binding(template)
	if binding_name:
		binding = frappe.get_doc("Visual Print Binding", binding_name)
		binding.enabled = 1
		binding.is_default = 1
		binding.show_on_form = 1
		binding.show_on_list = 1
		binding.save(ignore_permissions=True)
