import json

import frappe
from frappe.desk.doctype.list_view_settings.list_view_settings import set_listview_fields


def execute():
	doctype = "Production Exception Disposition"
	if not frappe.db.exists("DocType", doctype):
		frappe.throw("Production Exception Disposition DocType is missing")
	_configure_list(doctype)
	_ensure_workspace_link()
	_ensure_visual_print_template(doctype)


def _configure_list(doctype):
	fields = [
		{"label": "编号", "fieldname": "name"},
		{"label": "状态", "fieldname": "status_field"},
		{"label": "单据日期", "fieldname": "disposition_date"},
		{"label": "生产流转卡", "fieldname": "production_flow_card"},
		{"label": "工序报工单", "fieldname": "production_operation_report"},
		{"label": "异常类型", "fieldname": "exception_type"},
		{"label": "影响数量", "fieldname": "affected_qty"},
		{"label": "处置方式", "fieldname": "decision"},
	]
	if not frappe.db.exists("List View Settings", doctype):
		settings = frappe.new_doc("List View Settings")
		settings.name = doctype
		settings.fields = json.dumps(fields, ensure_ascii=False)
		settings.disable_scrolling = 0
		settings.save(ignore_permissions=True)
		visible = {field["fieldname"] for field in fields}
		current = [field.fieldname for field in frappe.get_meta(doctype).fields if field.in_list_view]
		set_listview_fields(doctype, fields, [name for name in current if name not in visible])
	if not frappe.db.get_global("production_exception_disposition_list_layout"):
		frappe.db.set_global("production_exception_disposition_list_layout", frappe.as_json({
			"widths": {"name": 155, "__status": 85, "disposition_date": 105, "production_flow_card": 145,
			           "production_operation_report": 145, "exception_type": 95, "affected_qty": 100, "decision": 100},
			"order": ["name", "__status", "disposition_date", "production_flow_card", "production_operation_report", "exception_type", "affected_qty", "decision"],
			"hidden": [], "sticky": ["name", "__status"],
		}))
	frappe.clear_cache(doctype=doctype)


def _ensure_workspace_link():
	if not frappe.db.exists("Workspace", "生产管理"):
		return
	workspace = frappe.get_doc("Workspace", "生产管理")
	if any(row.link_to == "Production Exception Disposition" for row in workspace.links):
		return
	card = next((row for row in workspace.links if row.type == "Card Break" and row.label == "生产执行"), None)
	if card:
		card.link_count = (card.link_count or 0) + 1
	workspace.append("links", {
		"type": "Link", "label": "生产异常处置单",
		"link_type": "DocType", "link_to": "Production Exception Disposition",
	})
	was_importing = frappe.flags.in_import
	frappe.flags.in_import = True
	try:
		workspace.save(ignore_permissions=True)
	finally:
		frappe.flags.in_import = was_importing


def _ensure_visual_print_template(doctype):
	if not frappe.db.exists("DocType", "Visual Print Template"):
		return
	from visual_print.bindings import ensure_template_binding
	from visual_print.visual_print_studio.page.visual_print_template_manager.visual_print_template_manager import (
		_default_visual_source_layout, _print_presentation, _visual_from_template_layout, save_visual_designer,
	)

	template_name = "生产异常处置单"
	if not frappe.db.exists("Visual Print Template", template_name):
		layout = _default_visual_source_layout(doctype, template_name)
		template = frappe.get_doc({
			"doctype": "Visual Print Template", "template_name": template_name,
			"doc_type": doctype, "module": frappe.get_meta(doctype).module,
			"purpose": "生产异常审核处置", "display_order": 0,
			"applicable_docstatus": "全部",
			"allowed_roles": "Manufacturing Manager\nSystem Manager",
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
