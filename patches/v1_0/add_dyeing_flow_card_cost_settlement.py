import json

import frappe
from frappe.desk.doctype.list_view_settings.list_view_settings import set_listview_fields


def execute():
	doctype = "Dyeing Flow Card Cost Settlement"
	if not frappe.db.exists("DocType", doctype):
		frappe.throw("Dyeing Flow Card Cost Settlement DocType is missing")
	_configure_list(doctype)
	_ensure_workspace_link()
	_ensure_visual_print_template(doctype)


def _configure_list(doctype):
	fields = [
		{"label": "编号", "fieldname": "name"},
		{"label": "状态", "fieldname": "status_field"},
		{"label": "结算日期", "fieldname": "settlement_date"},
		{"label": "生产流转卡", "fieldname": "production_flow_card"},
		{"label": "客户名称", "fieldname": "customer_name"},
		{"label": "已包装重量(Kg)", "fieldname": "output_weight"},
		{"label": "已归集成本", "fieldname": "total_cost"},
		{"label": "待计价行数", "fieldname": "unvalued_count"},
	]
	settings = frappe.get_doc("List View Settings", doctype) if frappe.db.exists("List View Settings", doctype) else frappe.new_doc("List View Settings")
	settings.name = doctype
	settings.fields = json.dumps(fields, ensure_ascii=False)
	settings.disable_scrolling = 0
	settings.save(ignore_permissions=True)
	visible = {field["fieldname"] for field in fields}
	current = [field.fieldname for field in frappe.get_meta(doctype).fields if field.in_list_view]
	set_listview_fields(doctype, fields, [name for name in current if name not in visible])
	frappe.db.set_global("dyeing_flow_card_cost_settlement_list_layout", frappe.as_json({
		"widths": {"name": 150, "__status": 85, "settlement_date": 105, "production_flow_card": 145, "customer_name": 160, "output_weight": 130, "total_cost": 120, "unvalued_count": 105},
		"order": ["name", "__status", "settlement_date", "production_flow_card", "customer_name", "output_weight", "total_cost", "unvalued_count"],
		"hidden": [], "sticky": ["name", "__status"],
	}))
	frappe.clear_cache(doctype=doctype)


def _ensure_workspace_link():
	if not frappe.db.exists("Workspace", "生产管理"):
		return
	workspace = frappe.get_doc("Workspace", "生产管理")
	card = next((row for row in workspace.links if row.type == "Card Break" and row.label == "成本管理"), None)
	if card:
		card.link_count = max(card.link_count or 0, 8)
	if not any(row.link_to == "Dyeing Flow Card Cost Settlement" for row in workspace.links):
		workspace.append("links", {"type": "Link", "label": "流转卡成本结算单", "link_type": "DocType", "link_to": "Dyeing Flow Card Cost Settlement"})
	workspace.save(ignore_permissions=True)


def _ensure_visual_print_template(doctype):
	if not frappe.db.exists("DocType", "Visual Print Template"):
		return
	from visual_print.bindings import ensure_template_binding
	from visual_print.visual_print_studio.page.visual_print_template_manager.visual_print_template_manager import (
		_default_visual_source_layout,
		_print_presentation,
		_visual_from_template_layout,
		save_visual_designer,
	)

	template_name = "流转卡成本结算单"
	if not frappe.db.exists("Visual Print Template", template_name):
		layout = _default_visual_source_layout(doctype, template_name)
		template = frappe.get_doc({
			"doctype": "Visual Print Template", "template_name": template_name,
			"doc_type": doctype, "module": frappe.get_meta(doctype).module,
			"purpose": "流转卡成本归集明细", "display_order": 0,
			"applicable_docstatus": "全部",
			"allowed_roles": "Manufacturing Manager\nAccounts Manager\nSystem Manager",
			"enabled": 1, "is_default": 1, "status": "Draft",
			"renderer": "Typst", "schema_version": 5, "pdf_standard": "PDF 1.7",
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
