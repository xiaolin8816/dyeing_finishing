import json

import frappe
from frappe.desk.doctype.list_view_settings.list_view_settings import set_listview_fields


LISTS = {
	"Dyeing Energy Meter": {
		"fields": [
			{"label": "表计编码", "fieldname": "name"},
			{"label": "表计名称", "fieldname": "meter_name"},
			{"label": "能源类型", "fieldname": "energy_type"},
			{"label": "计量范围", "fieldname": "scope_type"},
			{"label": "生产工段", "fieldname": "work_center"},
			{"label": "生产机台", "fieldname": "production_resource"},
			{"label": "计量单位", "fieldname": "uom"},
			{"label": "启用", "fieldname": "is_active"},
		],
		"widths": {
			"name": 140, "meter_name": 150, "energy_type": 90,
			"scope_type": 90, "work_center": 130, "production_resource": 130,
			"uom": 100, "is_active": 75,
		},
		"sticky": ["name", "meter_name"],
		"key": "dyeing_energy_meter_list_layout",
	},
	"Dyeing Energy Meter Reading": {
		"fields": [
			{"label": "编号", "fieldname": "name"},
			{"label": "状态", "fieldname": "status_field"},
			{"label": "抄表时间", "fieldname": "reading_time"},
			{"label": "表计数量", "fieldname": "meter_count"},
			{"label": "备注", "fieldname": "remarks"},
		],
		"widths": {
			"name": 145, "__status": 80, "reading_time": 160,
			"meter_count": 90, "remarks": 200,
		},
		"sticky": ["name", "__status"],
		"key": "dyeing_energy_meter_reading_list_layout",
	},
}


def execute():
	for doctype, spec in LISTS.items():
		if not frappe.db.exists("DocType", doctype):
			return
		_configure_list(doctype, spec)
	_ensure_workspace_links()
	for doctype, title, purpose in (
		("Dyeing Energy Meter", "能源表计档案", "能源表计资料"),
		("Dyeing Energy Meter Reading", "能源抄表单", "能源用量记录"),
	):
		_ensure_visual_print_template(doctype, title, purpose)


def _configure_list(doctype, spec):
	settings = (
		frappe.get_doc("List View Settings", doctype)
		if frappe.db.exists("List View Settings", doctype)
		else frappe.new_doc("List View Settings")
	)
	settings.name = doctype
	settings.fields = json.dumps(spec["fields"], ensure_ascii=False)
	settings.disable_scrolling = 0
	settings.save(ignore_permissions=True)
	visible = {field["fieldname"] for field in spec["fields"]}
	current = [field.fieldname for field in frappe.get_meta(doctype).fields if field.in_list_view]
	set_listview_fields(doctype, spec["fields"], [name for name in current if name not in visible])
	order = ["__status" if field["fieldname"] == "status_field" else field["fieldname"] for field in spec["fields"]]
	frappe.db.set_global(spec["key"], frappe.as_json({
		"widths": spec["widths"], "order": order, "hidden": [], "sticky": spec["sticky"],
	}))
	frappe.clear_cache(doctype=doctype)


def _ensure_workspace_links():
	if not frappe.db.exists("Workspace", "生产管理"):
		return
	workspace = frappe.get_doc("Workspace", "生产管理")
	card = next((row for row in workspace.links if row.type == "Card Break" and row.label == "成本管理"), None)
	if card:
		card.link_count = max(card.link_count or 0, 6)
	for doctype, label in (
		("Dyeing Energy Meter", "能源表计档案"),
		("Dyeing Energy Meter Reading", "能源抄表单"),
	):
		if not any(row.link_to == doctype for row in workspace.links):
			workspace.append("links", {
				"type": "Link", "label": label, "link_type": "DocType", "link_to": doctype,
			})
	workspace.save(ignore_permissions=True)


def _ensure_visual_print_template(doctype, template_name, purpose):
	if not frappe.db.exists("DocType", "Visual Print Template"):
		return
	from visual_print.bindings import ensure_template_binding
	from visual_print.visual_print_studio.page.visual_print_template_manager.visual_print_template_manager import (
		_default_visual_source_layout,
		_print_presentation,
		_visual_from_template_layout,
		save_visual_designer,
	)

	if not frappe.db.exists("Visual Print Template", template_name):
		layout = _default_visual_source_layout(doctype, template_name)
		template = frappe.get_doc({
			"doctype": "Visual Print Template", "template_name": template_name,
			"doc_type": doctype, "module": frappe.get_meta(doctype).module,
			"purpose": purpose, "display_order": 0,
			"applicable_docstatus": "全部",
			"allowed_roles": "Manufacturing User\nManufacturing Manager\nAccounts Manager\nSystem Manager",
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
