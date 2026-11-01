import json

import frappe
from frappe.desk.doctype.list_view_settings.list_view_settings import set_listview_fields


DOCTYPE = "Dyeing Cost Element"
WORKSPACE = "生产管理"
LIST_FIELDS = [
	{"label": "要素编码", "fieldname": "name"},
	{"label": "成本要素名称", "fieldname": "element_name"},
	{"label": "成本类别", "fieldname": "cost_category"},
	{"label": "成本性质", "fieldname": "cost_nature"},
	{"label": "成本习性", "fieldname": "cost_behavior"},
	{"label": "默认单位", "fieldname": "default_uom"},
	{"label": "默认计费方式", "fieldname": "default_calculation_basis"},
	{"label": "启用", "fieldname": "is_active"},
]
LIST_LAYOUT = {
	"widths": {
		"name": 130,
		"element_name": 180,
		"cost_category": 105,
		"cost_nature": 105,
		"cost_behavior": 105,
		"default_uom": 100,
		"default_calculation_basis": 125,
		"is_active": 80,
	},
	"order": [
		"name", "element_name", "cost_category", "cost_nature", "cost_behavior",
		"default_uom", "default_calculation_basis", "is_active",
	],
	"hidden": [],
	"sticky": ["name", "element_name"],
}

ELEMENTS = [
	("CE-GREY-FABRIC", "胚布材料", "胚布", "直接成本", "变动成本", "Kg", "按实际用量", 1, 1, 0, "全代料订单使用的胚布实际材料成本"),
	("CE-DYE", "染料", "染料", "直接成本", "变动成本", "Kg", "按实际用量", 1, 1, 0, "按确认配方和实际领退料归集"),
	("CE-AUXILIARY", "助剂", "助剂", "直接成本", "变动成本", "Kg", "按实际用量", 1, 1, 0, "按确认配方和实际领退料归集"),
	("CE-WATER", "生产用水", "水", "直接成本", "变动成本", "Cubic Meter", "每公斤", 1, 1, 1, "生产及清洗用水成本"),
	("CE-ELECTRICITY", "生产用电", "电", "直接成本", "变动成本", "Kilowatt-Hour", "每公斤", 1, 1, 1, "生产设备用电成本"),
	("CE-STEAM", "生产蒸汽", "蒸汽", "直接成本", "变动成本", "Tonne", "每公斤", 1, 1, 1, "染色及后整理蒸汽成本"),
	("CE-NATURAL-GAS", "生产天然气", "天然气", "直接成本", "变动成本", "Cubic Meter", "每公斤", 1, 1, 1, "锅炉或设备天然气成本"),
	("CE-WASTEWATER", "污水处理", "污水处理", "间接成本", "变动成本", "Cubic Meter", "每公斤", 1, 1, 1, "生产污水处理成本"),
	("CE-LABOR", "生产人工", "人工", "直接成本", "混合成本", "Hour", "每小时", 1, 1, 1, "生产岗位人工成本"),
	("CE-MACHINE", "机台运行成本", "机台", "直接成本", "混合成本", "Hour", "每小时", 1, 1, 1, "按生产机台实际或预计工时计算"),
	("CE-PACKAGING", "包装材料及人工", "包装", "直接成本", "变动成本", "Kg", "每公斤", 1, 1, 0, "包装材料和包装人工成本"),
	("CE-SUBCONTRACT", "委外加工", "委外", "直接成本", "变动成本", None, "按实际用量", 1, 1, 0, "委外加工和外部服务成本"),
	("CE-BATCH-OVERHEAD", "批次管理费用", "间接费用", "间接成本", "固定成本", None, "固定金额", 1, 1, 1, "按生产批次计提的管理费用"),
	("CE-OTHER", "其他生产成本", "其他", "间接成本", "混合成本", None, "按实际用量", 1, 1, 1, "未单独分类的其他生产成本"),
]

CATEGORY_ELEMENT = {
	"胚布": "CE-GREY-FABRIC",
	"染料": "CE-DYE",
	"助剂": "CE-AUXILIARY",
	"水": "CE-WATER",
	"电": "CE-ELECTRICITY",
	"蒸汽": "CE-STEAM",
	"天然气": "CE-NATURAL-GAS",
	"污水处理": "CE-WASTEWATER",
	"人工": "CE-LABOR",
	"机台": "CE-MACHINE",
	"包装": "CE-PACKAGING",
	"委外": "CE-SUBCONTRACT",
	"间接费用": "CE-BATCH-OVERHEAD",
	"其他": "CE-OTHER",
}


def execute():
	if not frappe.db.exists("DocType", DOCTYPE):
		return
	company = frappe.db.get_single_value("Global Defaults", "default_company") or frappe.db.get_value(
		"Company", {}, "name", order_by="creation"
	)
	if not company:
		return
	_create_elements(company)
	_migrate_rate_items()
	_migrate_estimate_items()
	_clean_reference_rate_data()
	_configure_list()
	_ensure_workspace_link()
	_ensure_visual_print_template()


def _create_elements(company):
	for values in ELEMENTS:
		code, name, category, nature, behavior, uom, basis, estimate, actual, allocation, description = values
		if frappe.db.exists(DOCTYPE, code):
			continue
		frappe.get_doc({
			"doctype": DOCTYPE,
			"element_code": code,
			"element_name": name,
			"cost_category": category,
			"cost_nature": nature,
			"cost_behavior": behavior,
			"default_uom": uom if uom and frappe.db.exists("UOM", uom) else None,
			"default_calculation_basis": basis,
			"enable_estimate": estimate,
			"enable_actual": actual,
			"enable_allocation": allocation,
			"company": company,
			"description": description,
		}).insert(ignore_permissions=True)


def _migrate_rate_items():
	if not frappe.db.exists("DocType", "Dyeing Cost Rate Standard Item"):
		return
	for row in frappe.get_all(
		"Dyeing Cost Rate Standard Item", fields=["name", "cost_category", "cost_item", "remarks"]
	):
		element = (
			"CE-BATCH-OVERHEAD"
			if row.cost_category == "其他" and "批次管理" in (row.cost_item or "")
			else CATEGORY_ELEMENT.get(row.cost_category, "CE-OTHER")
		)
		category = frappe.db.get_value(DOCTYPE, element, "cost_category") or row.cost_category
		cost_item = _clean_text(row.cost_item)
		remarks = _clean_text(row.remarks, replacement="参考")
		frappe.db.set_value(
			"Dyeing Cost Rate Standard Item",
			row.name,
			{"cost_element": element, "cost_category": category, "cost_item": cost_item, "remarks": remarks},
			update_modified=False,
		)


def _migrate_estimate_items():
	if not frappe.db.exists("DocType", "Dyeing Cost Estimate Item"):
		return
	for row in frappe.get_all("Dyeing Cost Estimate Item", fields=["name", "cost_category"]):
		frappe.db.set_value(
			"Dyeing Cost Estimate Item",
			row.name,
			"cost_element",
			CATEGORY_ELEMENT.get(row.cost_category, "CE-OTHER"),
			update_modified=False,
		)


def _clean_reference_rate_data():
	if not frappe.db.exists("DocType", "Dyeing Cost Rate Standard"):
		return
	for row in frappe.get_all("Dyeing Cost Rate Standard", fields=["name", "remarks"]):
		if "测试" not in (row.remarks or "") and "TEST_DATA_DYEING_COST_RATE_V1" not in (row.remarks or ""):
			continue
		frappe.db.set_value(
			"Dyeing Cost Rate Standard",
			row.name,
			"remarks",
			"初始参考费率。费率为测算假设，不代表企业最终财务标准，正式使用前请由生产、财务和能源管理人员共同复核。",
			update_modified=False,
		)


def _clean_text(value, replacement=""):
	value = (value or "").replace("（测试）", "").replace("(测试)", "")
	return value.replace("测试", replacement).strip()


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
	frappe.db.set_global("dyeing_cost_element_list_layout", frappe.as_json(LIST_LAYOUT))
	frappe.clear_cache(doctype=DOCTYPE)


def _ensure_workspace_link():
	if not frappe.db.exists("Workspace", WORKSPACE):
		return
	workspace = frappe.get_doc("Workspace", WORKSPACE)
	card = next((row for row in workspace.links if row.type == "Card Break" and row.label == "成本管理"), None)
	if card:
		card.link_count = max(card.link_count or 0, 3)
	else:
		workspace.append("links", {
			"type": "Card Break", "label": "成本管理", "link_type": "DocType", "link_count": 3,
		})
	if not any(row.link_to == DOCTYPE for row in workspace.links):
		workspace.append("links", {
			"type": "Link", "label": "成本要素档案", "link_type": "DocType", "link_to": DOCTYPE,
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

	template_name = "成本要素档案"
	if not frappe.db.exists("Visual Print Template", template_name):
		layout = _default_visual_source_layout(DOCTYPE, template_name)
		template = frappe.get_doc({
			"doctype": "Visual Print Template",
			"template_name": template_name,
			"doc_type": DOCTYPE,
			"module": frappe.get_meta(DOCTYPE).module,
			"purpose": "成本基础资料",
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
