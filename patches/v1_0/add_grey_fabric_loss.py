import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.desk.doctype.list_view_settings.list_view_settings import set_listview_fields


DOCTYPE = "Grey Fabric Loss"
LIST_FIELDS = [
	{"label": "编号", "fieldname": "name"},
	{"label": "状态", "fieldname": "status_field"},
	{"label": "客户名称", "fieldname": "customer_name"},
	{"label": "批次", "fieldname": "batch_summary"},
	{"label": "胚布名称", "fieldname": "item_name_summary"},
	{"label": "报损类型", "fieldname": "loss_type"},
	{"label": "报损匹数", "fieldname": "total_loss_roll_count"},
	{"label": "报损重量", "fieldname": "total_loss_weight"},
	{"label": "报损原因", "fieldname": "reason_details"},
	{"label": "单据日期", "fieldname": "loss_date"},
	{"label": "仓库", "fieldname": "warehouse"},
]
LIST_LAYOUT = {
	"widths": {
		"name": 125,
		"__status": 80,
		"customer_name": 120,
		"batch_summary": 145,
		"item_name_summary": 145,
		"loss_type": 95,
		"total_loss_roll_count": 85,
		"total_loss_weight": 90,
		"reason_details": 180,
		"loss_date": 100,
		"warehouse": 165,
	},
	"order": [
		"name", "__status", "customer_name", "batch_summary", "item_name_summary",
		"loss_type", "total_loss_roll_count", "total_loss_weight", "reason_details",
		"loss_date", "warehouse",
	],
	"hidden": [],
	"sticky": ["name", "__status"],
}


VISUAL_LABELS = {
	"loss_date": "单据日期",
	"batch_summary": "批次",
	"batch_no": "批次",
}


def _update_visual_labels(value):
	changed = False
	if isinstance(value, dict):
		fieldname = value.get("fieldname")
		label = VISUAL_LABELS.get(fieldname)
		if label and value.get("label") != label:
			value["label"] = label
			changed = True
		for child in value.values():
			changed = _update_visual_labels(child) or changed
	elif isinstance(value, list):
		for child in value:
			changed = _update_visual_labels(child) or changed
	return changed


def execute():
	_create_stock_links()
	_configure_list()
	_ensure_visual_print_template()


def _create_stock_links():
	create_custom_fields({
		"Stock Entry": [{
			"fieldname": "custom_grey_fabric_loss",
			"label": "胚布报损单",
			"fieldtype": "Link",
			"options": DOCTYPE,
			"insert_after": "custom_customer_grey_fabric_return",
			"read_only": 1,
			"no_copy": 1,
		}],
		"Stock Entry Detail": [{
			"fieldname": "custom_grey_fabric_loss",
			"label": "胚布报损单",
			"fieldtype": "Link",
			"options": DOCTYPE,
			"insert_after": "custom_customer_grey_fabric_return",
			"read_only": 1,
			"no_copy": 1,
		}],
	}, update=True)


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
	frappe.db.set_global("grey_fabric_loss_list_layout", frappe.as_json(LIST_LAYOUT))
	frappe.clear_cache(doctype=DOCTYPE)


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

	template_name = "胚布报损单"
	if not frappe.db.exists("Visual Print Template", template_name):
		layout = _default_visual_source_layout(DOCTYPE, template_name)
		doc = frappe.get_doc({
			"doctype": "Visual Print Template",
			"template_name": template_name,
			"doc_type": DOCTYPE,
			"module": frappe.get_meta(DOCTYPE).module,
			"purpose": "报损审批联",
			"display_order": 0,
			"applicable_docstatus": "已提交",
			"allowed_roles": "Stock User\nStock Manager\nSystem Manager",
			"enabled": 1,
			"is_default": 1,
			"status": "Draft",
			"renderer": "Typst",
			"schema_version": 5,
			"pdf_standard": "PDF 1.7",
			"layout_json": json.dumps(layout, ensure_ascii=False),
			"presentation_settings": json.dumps(_print_presentation("A4"), ensure_ascii=False),
		})
		doc.insert(ignore_permissions=True)
		visual = _visual_from_template_layout(doc, layout)
		save_visual_designer(doc.name, json.dumps(visual, ensure_ascii=False))

	template = frappe.get_doc("Visual Print Template", template_name)
	layout = frappe.parse_json(template.layout_json) or {}
	if _update_visual_labels(layout):
		visual = layout.get("visual_print_layout") or _visual_from_template_layout(template, layout)
		template.layout_json = json.dumps(layout, ensure_ascii=False)
		template.save(ignore_permissions=True)
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
