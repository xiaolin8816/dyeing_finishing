import json

import frappe


def execute():
	from dyeing_finishing.dyeing_finishing.doctype.outsourcing_processing_order.outsourcing_processing_order import (
		get_outsourcing_warehouse,
	)
	for company in frappe.get_all("Company", pluck="name"):
		get_outsourcing_warehouse(company)
	for row in frappe.get_all("Outsourcing Processing Order", fields=["name", "company"]):
		if row.company:
			frappe.db.set_value(
				"Outsourcing Processing Order", row.name, "supplier_warehouse",
				get_outsourcing_warehouse(row.company), update_modified=False,
			)
	from dyeing_finishing.patches.v1_0.add_outsourcing_management import _configure_list
	from dyeing_finishing.patches.v1_0.add_processing_contractor import _configure_contractor_list
	_configure_list()
	_configure_contractor_list()
	_refresh_system_visual_template("Outsourcing Processing Order", "委外加工单", "委外加工计划与审核")
	_refresh_system_visual_template("Processing Contractor", "加工商档案", "加工商资料")
	frappe.clear_cache(doctype="Warehouse")
	frappe.clear_cache(doctype="Outsourcing Processing Order")
	frappe.clear_cache(doctype="Processing Contractor")


def _refresh_system_visual_template(doctype, template_name, purpose):
	if not frappe.db.exists("Visual Print Template", template_name):
		return
	template = frappe.get_doc("Visual Print Template", template_name)
	if template.doc_type != doctype or template.purpose != purpose:
		return
	from visual_print.visual_print_studio.page.visual_print_template_manager.visual_print_template_manager import (
		_default_visual_source_layout, _print_presentation, _visual_from_template_layout, save_visual_designer,
	)
	layout = _default_visual_source_layout(doctype, template_name)
	if doctype == "Outsourcing Processing Order":
		fields = layout["sections"][0]["columns"][0]["fields"]
		if not any(field.get("fieldname") == "supplier_warehouse" for field in fields):
			fields.append({
				"fieldname": "supplier_warehouse", "label": "委外加工仓",
				"fieldtype": "Data", "align": "auto",
			})
	template.layout_json = json.dumps(layout, ensure_ascii=False)
	template.presentation_settings = json.dumps(_print_presentation("A4"), ensure_ascii=False)
	template.save(ignore_permissions=True)
	visual = _visual_from_template_layout(template, layout)
	save_visual_designer(template.name, json.dumps(visual, ensure_ascii=False))
