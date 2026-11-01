import json

import frappe
from frappe.desk.doctype.list_view_settings.list_view_settings import set_listview_fields


DOCTYPE = "Dyeing Cost Estimate"
WORKSPACE = "生产管理"
LIST_FIELDS = [
	{"label": "编号", "fieldname": "name"},
	{"label": "状态", "fieldname": "status_field"},
	{"label": "客户名称", "fieldname": "customer_name"},
	{"label": "染整销售订单", "fieldname": "sales_order"},
	{"label": "成品名称", "fieldname": "finished_product_name"},
	{"label": "颜色", "fieldname": "color"},
	{"label": "订单类型", "fieldname": "order_type"},
	{"label": "测算数量", "fieldname": "estimate_qty"},
	{"label": "预计总成本", "fieldname": "total_cost"},
	{"label": "预计单位成本", "fieldname": "unit_cost"},
	{"label": "预计毛利", "fieldname": "gross_profit"},
	{"label": "预计毛利率(%)", "fieldname": "gross_margin_rate"},
	{"label": "单据日期", "fieldname": "estimate_date"},
]
LIST_LAYOUT = {
	"widths": {
		"name": 135,
		"__status": 80,
		"customer_name": 135,
		"sales_order": 135,
		"finished_product_name": 150,
		"color": 90,
		"order_type": 90,
		"estimate_qty": 90,
		"total_cost": 105,
		"unit_cost": 105,
		"gross_profit": 105,
		"gross_margin_rate": 100,
		"estimate_date": 100,
	},
	"order": [
		"name", "__status", "customer_name", "sales_order", "finished_product_name",
		"color", "order_type", "estimate_qty", "total_cost", "unit_cost",
		"gross_profit", "gross_margin_rate", "estimate_date",
	],
	"hidden": [],
	"sticky": ["name", "__status", "customer_name"],
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
	frappe.db.set_global("dyeing_cost_estimate_list_layout", frappe.as_json(LIST_LAYOUT))
	frappe.clear_cache(doctype=DOCTYPE)


def _ensure_workspace_link():
	if not frappe.db.exists("Workspace", WORKSPACE):
		return
	workspace = frappe.get_doc("Workspace", WORKSPACE)
	content = frappe.parse_json(workspace.content) or []
	card_id = "生产管理-成本管理-card"
	if not any(block.get("id") == "生产管理-成本管理-header" for block in content):
		content.append({
			"id": "生产管理-成本管理-header",
			"type": "header",
			"data": {"text": '<span class="h4"><b>成本管理</b></span>', "col": 12},
		})
	if not any(block.get("id") == card_id for block in content):
		content.append({
			"id": card_id,
			"type": "card",
			"data": {"card_name": "成本管理", "col": 4},
		})
	workspace.content = json.dumps(content, ensure_ascii=False, separators=(",", ":"))

	if not any(row.type == "Card Break" and row.label == "成本管理" for row in workspace.links):
		workspace.append("links", {
			"type": "Card Break",
			"label": "成本管理",
			"link_type": "DocType",
			"link_count": 1,
		})
	if not any(row.link_to == DOCTYPE for row in workspace.links):
		workspace.append("links", {
			"type": "Link",
			"label": "染整成本测算单",
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

	template_name = "染整成本测算单"
	if not frappe.db.exists("Visual Print Template", template_name):
		layout = _default_visual_source_layout(DOCTYPE, template_name)
		template = frappe.get_doc({
			"doctype": "Visual Print Template",
			"template_name": template_name,
			"doc_type": DOCTYPE,
			"module": frappe.get_meta(DOCTYPE).module,
			"purpose": "成本测算审批",
			"display_order": 0,
			"applicable_docstatus": "全部",
			"allowed_roles": "Sales User\nSales Manager\nManufacturing Manager\nSystem Manager",
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
