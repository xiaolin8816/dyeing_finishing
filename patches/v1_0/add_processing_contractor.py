import json

import frappe
from frappe.desk.doctype.list_view_settings.list_view_settings import set_listview_fields


CONTRACTOR_DOCTYPE = "Processing Contractor"
CONTRACTOR_LIST_FIELDS = [
	{"label": "编号", "fieldname": "name"},
	{"label": "状态", "fieldname": "status"},
	{"label": "加工商名称", "fieldname": "contractor_name"},
	{"label": "关联结算供应商", "fieldname": "supplier_name"},
	{"label": "可承接加工", "fieldname": "processing_types"},
	{"label": "联系人", "fieldname": "contact_person"},
	{"label": "联系电话", "fieldname": "contact_phone"},
	{"label": "默认计价方式", "fieldname": "default_pricing_basis"},
	{"label": "默认加工单价", "fieldname": "default_unit_rate"},
	{"label": "质量等级", "fieldname": "quality_grade"},
]
CONTRACTOR_LIST_LAYOUT = {
	"widths": {"name": 140, "status": 80, "contractor_name": 160, "supplier_name": 160,
		"processing_types": 180, "contact_person": 100, "contact_phone": 125,
		"default_pricing_basis": 105, "default_unit_rate": 110, "quality_grade": 90},
	"order": [field["fieldname"] for field in CONTRACTOR_LIST_FIELDS],
	"hidden": [],
	"sticky": ["name", "status", "contractor_name"],
}


def execute():
	if not frappe.db.exists("DocType", CONTRACTOR_DOCTYPE):
		frappe.throw("Processing Contractor DocType is missing")
	_migrate_existing_orders()
	_rename_resource_type()
	_configure_contractor_list()
	from dyeing_finishing.patches.v1_0.add_outsourcing_management import (
		_configure_list, _sync_root_workspace, _sync_sidebar_source, _sync_workspace,
	)
	_configure_list()
	_sync_workspace("委外管理")
	_sync_root_workspace()
	_sync_sidebar_source()
	_ensure_visual_print_template()
	frappe.clear_cache(doctype=CONTRACTOR_DOCTYPE)
	frappe.clear_cache(doctype="Outsourcing Processing Order")


def _migrate_existing_orders():
	if not frappe.db.has_column("Outsourcing Processing Order", "processing_contractor"):
		return
	rows = frappe.get_all(
		"Outsourcing Processing Order",
		filters={"supplier": ["is", "set"], "processing_contractor": ["is", "not set"]},
		fields=["name", "supplier", "supplier_name", "supplier_warehouse", "supplier_contact", "supplier_phone", "currency", "company"],
	)
	for row in rows:
		contractor = frappe.db.get_value(CONTRACTOR_DOCTYPE, {"supplier": row.supplier}, "name")
		if not contractor:
			contractor_doc = frappe.get_doc({
				"doctype": CONTRACTOR_DOCTYPE,
				"contractor_name": row.supplier_name or frappe.db.get_value("Supplier", row.supplier, "supplier_name"),
				"status": "启用",
				"supplier": row.supplier,
				"supplier_name": row.supplier_name,
				"contact_person": row.supplier_contact,
				"contact_phone": row.supplier_phone,
				"currency": row.currency or frappe.db.get_value("Company", row.company, "default_currency"),
				"company": row.company,
			})
			contractor_doc.insert(ignore_permissions=True)
			contractor = contractor_doc.name
		frappe.db.set_value("Outsourcing Processing Order", row.name, {
			"processing_contractor": contractor,
			"processing_contractor_name": frappe.db.get_value(CONTRACTOR_DOCTYPE, contractor, "contractor_name"),
		}, update_modified=False)


def _rename_resource_type():
	for doctype in ("Production Resource", "Production Operation"):
		if frappe.db.exists("DocType", doctype):
			for name in frappe.get_all(doctype, filters={"resource_type": "委外供应商"}, pluck="name"):
				frappe.db.set_value(doctype, name, "resource_type", "加工商", update_modified=False)


def _configure_contractor_list():
	settings = frappe.get_doc("List View Settings", CONTRACTOR_DOCTYPE) if frappe.db.exists(
		"List View Settings", CONTRACTOR_DOCTYPE
	) else frappe.new_doc("List View Settings")
	settings.name = CONTRACTOR_DOCTYPE
	settings.fields = json.dumps(CONTRACTOR_LIST_FIELDS, ensure_ascii=False)
	settings.disable_scrolling = 0
	settings.save(ignore_permissions=True)
	visible = {field["fieldname"] for field in CONTRACTOR_LIST_FIELDS}
	current = [field.fieldname for field in frappe.get_meta(CONTRACTOR_DOCTYPE).fields if field.in_list_view]
	set_listview_fields(CONTRACTOR_DOCTYPE, CONTRACTOR_LIST_FIELDS, [field for field in current if field not in visible])
	frappe.db.set_global("processing_contractor_list_layout", frappe.as_json(CONTRACTOR_LIST_LAYOUT))


def _ensure_visual_print_template():
	if not frappe.db.exists("DocType", "Visual Print Template"):
		return
	from visual_print.bindings import ensure_template_binding
	from visual_print.visual_print_studio.page.visual_print_template_manager.visual_print_template_manager import (
		_default_visual_source_layout, _print_presentation, _visual_from_template_layout, save_visual_designer,
	)
	template_name = "加工商档案"
	if not frappe.db.exists("Visual Print Template", template_name):
		layout = _default_visual_source_layout(CONTRACTOR_DOCTYPE, template_name)
		template = frappe.get_doc({
			"doctype": "Visual Print Template", "template_name": template_name, "doc_type": CONTRACTOR_DOCTYPE,
			"module": frappe.get_meta(CONTRACTOR_DOCTYPE).module, "purpose": "加工商资料",
			"display_order": 0, "applicable_docstatus": "全部",
			"allowed_roles": "Manufacturing Manager\nPurchase Manager\nSystem Manager",
			"enabled": 1, "is_default": 1, "status": "Draft", "renderer": "Typst", "schema_version": 5,
			"pdf_standard": "PDF 1.7", "layout_json": json.dumps(layout, ensure_ascii=False),
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
