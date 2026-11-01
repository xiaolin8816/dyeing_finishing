import frappe
from frappe.utils import nowdate


REFERENCE_NOTE = "初始参考费率"
CATEGORY_ELEMENT = {
	"水": "CE-WATER",
	"电": "CE-ELECTRICITY",
	"蒸汽": "CE-STEAM",
	"天然气": "CE-NATURAL-GAS",
	"污水处理": "CE-WASTEWATER",
	"人工": "CE-LABOR",
	"机台": "CE-MACHINE",
	"包装": "CE-PACKAGING",
	"其他": "CE-BATCH-OVERHEAD",
}


def execute():
	if frappe.db.exists("Dyeing Cost Rate Standard", {"remarks": ["like", f"%{REFERENCE_NOTE}%"]}) or frappe.db.exists(
		"Dyeing Cost Rate Standard", {"remarks": ["like", "%TEST_DATA_DYEING_COST_RATE_V1%"]}
	):
		return
	company = frappe.db.get_single_value("Global Defaults", "default_company") or frappe.db.get_value(
		"Company", {}, "name", order_by="creation"
	)
	if not company:
		return

	resource_rates = {
		"RES-DYE-100": 65,
		"RES-DYE-300": 90,
		"RES-DYE-500": 120,
	}
	rate_items = [
		_rate_item("水", "生产用水", "每公斤", 0.08, "Cubic Meter", 3.50, "按每公斤布耗水 0.08 立方米参考"),
		_rate_item("电", "生产用电", "每公斤", 0.12, "Kilowatt-Hour", 0.85, "按每公斤布耗电 0.12 千瓦时参考"),
		_rate_item("蒸汽", "生产蒸汽", "每公斤", 0.006, "Tonne", 260, "按每公斤布耗蒸汽 0.006 吨参考"),
		_rate_item("天然气", "生产天然气", "每公斤", 0.03, "Cubic Meter", 3.80, "按每公斤布耗气 0.03 立方米参考"),
		_rate_item("污水处理", "污水处理", "每公斤", 0.07, "Cubic Meter", 4.50, "按每公斤布产生污水 0.07 立方米参考"),
		_rate_item("人工", "生产人工", "每小时", 2, "Hour", 28, "按每生产小时投入 2 人参考"),
		_rate_item("包装", "包装材料及人工", "每公斤", 1, "Kg", 0.15, "按成品重量计提参考包装费"),
		_rate_item("其他", "批次管理费用", "固定金额", 1, None, 50, "每批固定管理费用参考"),
	]
	for resource, hourly_rate in resource_rates.items():
		if frappe.db.exists("Production Resource", resource):
			rate_items.append(_rate_item(
				"机台",
				f"{resource} 机台费",
				"每小时",
				1,
				"Hour",
				hourly_rate,
				"按计划生产机台和预计生产工时计算",
				production_resource=resource,
				work_center=frappe.db.get_value("Production Resource", resource, "work_center"),
			))

	doc = frappe.get_doc({
		"doctype": "Dyeing Cost Rate Standard",
		"standard_date": nowdate(),
		"effective_from": nowdate(),
		"applicable_order_type": "全部",
		"company": company,
		"remarks": (
			f"{REFERENCE_NOTE}。费率为测算假设，不代表企业最终财务标准，"
			"正式使用前请由生产、财务和能源管理人员共同复核。"
		),
		"rate_items": rate_items,
	})
	doc.insert(ignore_permissions=True)
	doc.submit()


def _rate_item(
	cost_category,
	cost_item,
	calculation_basis,
	standard_consumption,
	uom,
	unit_rate,
	remarks,
	production_resource=None,
	work_center=None,
):
	return {
		"cost_element": CATEGORY_ELEMENT[cost_category],
		"cost_category": cost_category,
		"cost_item": cost_item,
		"calculation_basis": calculation_basis,
		"standard_consumption": standard_consumption,
		"uom": uom,
		"unit_rate": unit_rate,
		"production_resource": production_resource,
		"work_center": work_center,
		"remarks": remarks,
	}
