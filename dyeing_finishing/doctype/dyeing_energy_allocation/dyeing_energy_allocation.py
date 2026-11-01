from decimal import Decimal, ROUND_HALF_UP

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, getdate, nowdate


ENERGY_COST_ELEMENTS = {
	"水": "CE-WATER",
	"电": "CE-ELECTRICITY",
	"蒸汽": "CE-STEAM",
	"天然气": "CE-NATURAL-GAS",
	"污水处理": "CE-WASTEWATER",
}


def _decimal(value):
	return Decimal(str(value or 0))


def split_amount(total, weights, places=6):
	weights = [_decimal(weight) for weight in weights]
	weight_total = sum(weights)
	if not weights or weight_total <= 0 or any(weight <= 0 for weight in weights):
		frappe.throw(_("分摊依据必须全部大于零"))
	unit = Decimal(10) ** -places
	total = _decimal(total).quantize(unit, rounding=ROUND_HALF_UP)
	if total < 0:
		frappe.throw(_("分摊数量不能小于零"))
	total_units = int(total / unit)
	raw_units = [Decimal(total_units) * weight / weight_total for weight in weights]
	allocated = [int(value) for value in raw_units]
	remainder = total_units - sum(allocated)
	order = sorted(range(len(weights)), key=lambda index: (raw_units[index] - allocated[index], -index), reverse=True)
	for index in order[:remainder]:
		allocated[index] += 1
	return [Decimal(value) * unit for value in allocated]


def _meter_scopes_overlap(left, right):
	if left.energy_type != right.energy_type:
		return False
	if "总表" in (left.scope_type, right.scope_type):
		return True
	if left.scope_type == right.scope_type == "工段":
		return left.work_center == right.work_center
	if left.scope_type == right.scope_type == "机台":
		return left.production_resource == right.production_resource
	center = left if left.scope_type == "工段" else right
	machine = left if left.scope_type == "机台" else right
	return center.work_center == machine.work_center


def _applicable_rate(rate_standard, meter):
	if not rate_standard:
		return None, Decimal(0)
	matches = []
	for row in rate_standard.rate_items:
		if row.cost_element != ENERGY_COST_ELEMENTS.get(meter.energy_type) or row.uom != meter.uom:
			continue
		if row.production_resource and row.production_resource != meter.production_resource:
			continue
		if row.work_center and row.work_center != meter.work_center:
			continue
		if row.production_operation:
			continue
		specificity = int(bool(row.production_resource)) * 2 + int(bool(row.work_center))
		matches.append((specificity, row))
	if not matches:
		frappe.throw(_("表计 {0} 在所选费率标准中没有适用费率").format(meter.meter))
	best = max(score for score, _ in matches)
	selected = [row for score, row in matches if score == best]
	if len(selected) != 1:
		frappe.throw(_("表计 {0} 对应多个同范围费率").format(meter.meter))
	return selected[0].cost_element, _decimal(selected[0].unit_rate)


def _actual_basis(actual, start, end, basis):
	actual_start, actual_end = get_datetime(actual.actual_start), get_datetime(actual.actual_end)
	seconds = (min(actual_end, end) - max(actual_start, start)).total_seconds()
	if seconds <= 0:
		return Decimal(0)
	if basis == "按实际工时":
		return Decimal(str(seconds)) / Decimal(3600)
	if actual.uom != "Kg":
		frappe.throw(_("实绩单 {0} 的合格重量单位不是 Kg").format(actual.name))
	return _decimal(actual.completed_qty) * Decimal(str(seconds)) / Decimal(
		str((actual_end - actual_start).total_seconds())
	)


def build_allocation_rows(source_reading, basis, rate_standard=None):
	if basis not in ("按实际工时", "按合格重量"):
		frappe.throw(_("请选择有效的分摊依据"))
	reading = frappe.get_doc("Dyeing Energy Meter Reading", source_reading)
	if reading.docstatus == 2:
		frappe.throw(_("不能引用已取消的抄表单"))
	if not reading.items:
		frappe.throw(_("来源抄表单没有明细"))
	if rate_standard:
		standard = frappe.get_doc("Dyeing Cost Rate Standard", rate_standard)
		if standard.docstatus != 1 or standard.company != reading.company:
			frappe.throw(_("费率标准须已提交且所属公司一致"))
		reading_date = getdate(reading.reading_time)
		if reading_date < getdate(standard.effective_from) or (
			standard.effective_to and reading_date > getdate(standard.effective_to)
		):
			frappe.throw(_("费率标准在抄表日期无效"))
	else:
		standard = None

	meters = list(reading.items)
	for index, left in enumerate(meters):
		for right in meters[index + 1:]:
			if _meter_scopes_overlap(left, right):
				frappe.throw(_("表计 {0} 与 {1} 计量范围重叠，请先核定主子表关系").format(left.meter, right.meter))

	results = []
	for meter in meters:
		consumption = _decimal(meter.consumption)
		if consumption < 0:
			frappe.throw(_("表计 {0} 用量不能小于零").format(meter.meter))
		if consumption == 0:
			continue
		if meter.previous_source:
			previous = frappe.get_doc("Dyeing Energy Meter Reading", meter.previous_source)
			if previous.docstatus != 1 or previous.company != reading.company:
				frappe.throw(_("表计 {0} 的上次抄表单无效").format(meter.meter))
			start = get_datetime(previous.reading_time)
		else:
			start = get_datetime(frappe.db.get_value("Dyeing Energy Meter", meter.meter, "opening_time"))
		end = get_datetime(reading.reading_time)
		if end <= start:
			frappe.throw(_("表计 {0} 的抄表区间无效").format(meter.meter))

		actuals = frappe.get_all(
			"Dyeing Production Actual",
			filters={
				"docstatus": 1, "company": reading.company,
				"actual_start": ["<", end], "actual_end": [">", start],
			},
			fields=[
				"name", "production_flow_card", "production_resource", "actual_start",
				"actual_end", "completed_qty", "uom",
			],
			order_by="actual_start asc, name asc",
			limit_page_length=0,
		)
		if meter.scope_type == "机台":
			actuals = [actual for actual in actuals if actual.production_resource == meter.production_resource]
		elif meter.scope_type == "工段":
			resources = set(frappe.get_all(
				"Production Resource", filters={"work_center": meter.work_center}, pluck="name"
			))
			actuals = [actual for actual in actuals if actual.production_resource in resources]
		elif meter.scope_type != "总表":
			frappe.throw(_("表计 {0} 的计量范围无效").format(meter.meter))
		actuals = [actual for actual in actuals if actual.production_flow_card]
		weights = [_actual_basis(actual, start, end, basis) for actual in actuals]
		eligible = [(actual, weight) for actual, weight in zip(actuals, weights) if weight > 0]
		if not eligible:
			frappe.throw(_("表计 {0} 在抄表区间内没有可分摊的已提交生产实绩").format(meter.meter))
		actuals, weights = zip(*eligible)
		basis_total = sum(weights)
		quantities = split_amount(consumption, weights)
		cost_element, unit_rate = _applicable_rate(standard, meter)
		amounts = split_amount(consumption * unit_rate, weights, places=2)
		for actual, weight, quantity, amount in zip(actuals, weights, quantities, amounts):
			results.append({
				"source_reading_item": meter.name,
				"meter": meter.meter,
				"meter_name": meter.meter_name,
				"energy_type": meter.energy_type,
				"uom": meter.uom,
				"period_start": start,
				"period_end": end,
				"source_consumption": float(consumption),
				"production_actual": actual.name,
				"production_flow_card": actual.production_flow_card,
				"production_resource": actual.production_resource,
				"basis_value": float(weight.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)),
				"basis_total": float(basis_total.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)),
				"allocated_consumption": float(quantity),
				"cost_element": cost_element,
				"unit_rate": float(unit_rate),
				"estimated_amount": float(amount),
			})
	return reading, results


class DyeingEnergyAllocation(Document):
	def before_insert(self):
		self.allocation_no = self.name
		self.allocation_status = "草稿"

	def validate(self):
		self.allocation_no = self.name
		self.allocation_date = self.allocation_date or nowdate()
		if not self.source_reading:
			frappe.throw(_("请选择来源抄表单"))
		reading, expected = build_allocation_rows(
			self.source_reading, self.allocation_basis, self.rate_standard
		)
		if getdate(self.allocation_date) < getdate(reading.reading_time):
			frappe.throw(_("分摊日期不能早于来源抄表日期"))
		self.company = reading.company
		if self.docstatus == 1 and reading.docstatus != 1:
			frappe.throw(_("正式分摊必须引用已提交的抄表单"))
		self.set("items", [])
		for values in expected:
			self.append("items", values)
		self.meter_count = len({row["meter"] for row in expected})
		self.line_count = len(expected)
		self.total_amount = float(sum((_decimal(row["estimated_amount"]) for row in expected), Decimal(0)))
		self.currency = frappe.db.get_value("Company", self.company, "default_currency")
		if self.docstatus == 0:
			self.allocation_status = "草稿"

	def before_submit(self):
		frappe.db.sql(
			"SELECT name FROM `tabDyeing Energy Meter Reading` WHERE name = %s FOR UPDATE",
			self.source_reading,
		)
		if frappe.db.get_value("Dyeing Energy Meter Reading", self.source_reading, "docstatus") != 1:
			frappe.throw(_("请先提交来源抄表单"))
		if frappe.db.exists("Dyeing Energy Allocation", {
			"source_reading": self.source_reading, "docstatus": 1, "name": ["!=", self.name],
		}):
			frappe.throw(_("此抄表单已存在已提交的生产能源分摊单"))
		self.validate()
		for actual in sorted({row.production_actual for row in self.items}):
			frappe.db.sql(
				"SELECT name FROM `tabDyeing Production Actual` WHERE name = %s FOR UPDATE", actual
			)
			if frappe.db.get_value("Dyeing Production Actual", actual, "docstatus") != 1:
				frappe.throw(_("实绩单 {0} 已取消，请重新生成分摊").format(actual))
		self.validate()
		if not self.items:
			frappe.throw(_("没有可提交的分摊明细"))
		self.allocation_status = "已提交"

	def on_cancel(self):
		self.db_set("allocation_status", "已取消", update_modified=False)


@frappe.whitelist()
def get_allocation_preview(source_reading, allocation_basis, rate_standard=None):
	frappe.has_permission("Dyeing Energy Allocation", ptype="create", throw=True)
	frappe.has_permission("Dyeing Production Actual", ptype="read", throw=True)
	reading = frappe.get_doc("Dyeing Energy Meter Reading", source_reading)
	reading.check_permission("read")
	if rate_standard:
		frappe.get_doc("Dyeing Cost Rate Standard", rate_standard).check_permission("read")
	_, rows = build_allocation_rows(source_reading, allocation_basis, rate_standard)
	return {"company": reading.company, "source_docstatus": reading.docstatus, "rows": rows}
