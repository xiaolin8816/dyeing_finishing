import json

import frappe
from frappe.desk.doctype.list_view_settings.list_view_settings import set_listview_fields


DOCTYPE = "Dyeing Cost Rate Standard"
WORKSPACE = "生产管理"
LIST_FIELDS = [
	{"label": "编号", "fieldname": "name"},
	{"label": "状态", "fieldname": "status_field"},
	{"label": "标准版本", "fieldname": "standard_version"},
	{"label": "生效日期", "fieldname": "effective_from"},
	{"label": "失效日期", "fieldname": "effective_to"},
	{"label": "适用订单类型", "fieldname": "applicable_order_type"},
	{"label": "费率项目数", "fieldname": "rate_item_count"},
	{"label": "单据日期", "fieldname": "standard_date"},
]
LIST_LAYOUT = {
	"widths": {
		"name": 145,
		"__status": 80,
		"standard_version": 90,
		"effective_from": 105,
		"effective_to": 105,
		"applicable_order_type": 115,
		"rate_item_count": 95,
		"standard_date": 105,
	},
	"order": [
		"name", "__status", "standard_version", "effective_from", "effective_to",
		"applicable_order_type", "rate_item_count", "standard_date",
	],
	"hidden": [],
	"sticky": ["name", "__status"],
}


def execute():
	_configure_list()
	_ensure_workspace_link()
	_ensure_visual_print_template()


def _configure_list():
	if not frappe.db.exists("DocType", DOCTYPE):
		return
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
	frappe.db.set_global("dyeing_cost_rate_standard_list_layout", frappe.as_json(LIST_LAYOUT))
	frappe.clear_cache(doctype=DOCTYPE)


def _ensure_workspace_link():
	if not frappe.db.exists("Workspace", WORKSPACE):
		return
	workspace = frappe.get_doc("Workspace", WORKSPACE)
	card = next((row for row in workspace.links if row.type == "Card Break" and row.label == "成本管理"), None)
	if card:
		card.link_count = max(card.link_count or 0, 2)
	else:
		workspace.append("links", {
			"type": "Card Break",
			"label": "成本管理",
			"link_type": "DocType",
			"link_count": 2,
		})
	if not any(row.link_to == DOCTYPE for row in workspace.links):
		workspace.append("links", {
			"type": "Link",
			"label": "染整成本费率标准",
			"link_type": "DocType",
			"link_to": DOCTYPE,
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

	template_name = "染整成本费率标准"
	if not frappe.db.exists("Visual Print Template", template_name):
		layout = _default_visual_source_layout(DOCTYPE, template_name)
		template = frappe.get_doc({
			"doctype": "Visual Print Template",
			"template_name": template_name,
			"doc_type": DOCTYPE,
			"module": frappe.get_meta(DOCTYPE).module,
			"purpose": "成本费率审批",
			"display_order": 0,
			"applicable_docstatus": "全部",
			"allowed_roles": "Accounts Manager\nManufacturing Manager\nSales Manager\nSystem Manager",
			"enabled": 1,
			"is_default": 1,
			"status": "Draft",
			"renderer": "Typst",
			"schema_version": 5,
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
