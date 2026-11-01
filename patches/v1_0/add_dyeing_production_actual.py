import json

import frappe
from frappe.desk.doctype.list_view_settings.list_view_settings import set_listview_fields


DOCTYPE = "Dyeing Production Actual"
LIST_FIELDS = [
	{"label": "编号", "fieldname": "name"},
	{"label": "状态", "fieldname": "status_field"},
	{"label": "单据日期", "fieldname": "actual_date"},
	{"label": "缸号", "fieldname": "vat_no"},
	{"label": "客户名称", "fieldname": "customer_name"},
	{"label": "生产流转卡", "fieldname": "production_flow_card"},
	{"label": "工序报工单", "fieldname": "production_operation_report"},
	{"label": "工序名称", "fieldname": "operation_name"},
	{"label": "生产机台", "fieldname": "production_resource"},
	{"label": "实际开始", "fieldname": "actual_start"},
	{"label": "实际结束", "fieldname": "actual_end"},
	{"label": "实际工时", "fieldname": "actual_hours"},
	{"label": "合格数量", "fieldname": "completed_qty"},
]
LIST_LAYOUT = {
	"widths": {
		"name": 145, "__status": 80, "actual_date": 100, "vat_no": 100,
		"customer_name": 140, "production_flow_card": 145,
		"production_operation_report": 145, "operation_name": 100,
		"production_resource": 120, "actual_start": 145, "actual_end": 145,
		"actual_hours": 95, "completed_qty": 95,
	},
	"order": [
		"name", "__status", "actual_date", "vat_no", "customer_name",
		"production_flow_card", "production_operation_report", "operation_name",
		"production_resource", "actual_start", "actual_end", "actual_hours", "completed_qty",
	],
	"hidden": [],
	"sticky": ["name", "__status", "vat_no"],
}


def execute():
	if not frappe.db.exists("DocType", DOCTYPE):
		return
	_configure_list()
	_ensure_workspace_link()
	_ensure_visual_print_template()


def _configure_list():
	settings = (
		frappe.get_doc("List View Settings", DOCTYPE)
		if frappe.db.exists("List View Settings", DOCTYPE)
		else frappe.new_doc("List View Settings")
	)
	settings.name = DOCTYPE
	settings.fields = json.dumps(LIST_FIELDS, ensure_ascii=False)
	settings.disable_scrolling = 0
	settings.save(ignore_permissions=True)
	meta = frappe.get_meta(DOCTYPE)
	visible = {field["fieldname"] for field in LIST_FIELDS}
	current = [field.fieldname for field in meta.fields if field.in_list_view]
	set_listview_fields(DOCTYPE, LIST_FIELDS, [field for field in current if field not in visible])
	frappe.db.set_global("dyeing_production_actual_list_layout", frappe.as_json(LIST_LAYOUT))
	frappe.clear_cache(doctype=DOCTYPE)


def _ensure_workspace_link():
	if not frappe.db.exists("Workspace", "生产管理"):
		return
	workspace = frappe.get_doc("Workspace", "生产管理")
	card = next((row for row in workspace.links if row.type == "Card Break" and row.label == "成本管理"), None)
	if card:
		card.link_count = max(card.link_count or 0, 4)
	if not any(row.link_to == DOCTYPE for row in workspace.links):
		workspace.append("links", {
			"type": "Link", "label": "染色生产实绩单",
			"link_type": "DocType", "link_to": DOCTYPE,
		})
		workspace.save(ignore_permissions=True)


def _ensure_visual_print_template():
	if not frappe.db.exists("DocType", "Visual Print Template"):
		return
	from visual_print.bindings import ensure_template_binding
	from visual_print.visual_print_studio.page.visual_print_template_manager.visual_print_template_manager import (
		_default_visual_source_layout,
		_print_presentation,
		_visual_from_template_layout,
		save_visual_designer,
	)

	template_name = "染色生产实绩单"
	if not frappe.db.exists("Visual Print Template", template_name):
		layout = _default_visual_source_layout(DOCTYPE, template_name)
		template = frappe.get_doc({
			"doctype": "Visual Print Template", "template_name": template_name,
			"doc_type": DOCTYPE, "module": frappe.get_meta(DOCTYPE).module,
			"purpose": "生产实绩记录", "display_order": 0,
			"applicable_docstatus": "全部",
			"allowed_roles": "Manufacturing User\nManufacturing Manager\nSystem Manager",
			"enabled": 1, "is_default": 1, "status": "Draft",
			"renderer": "Typst", "schema_version": 5,
			"pdf_standard": "PDF 1.7",
			"layout_json": json.dumps(layout, ensure_ascii=False),
			"presentation_settings": json.dumps(_print_presentation("A4"), ensure_ascii=False),
		})
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
