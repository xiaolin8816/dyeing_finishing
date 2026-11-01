from decimal import Decimal, ROUND_HALF_UP

import frappe
from frappe import _
from frappe.desk.reportview import get_match_cond
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, nowdate

from dyeing_finishing.dyeing_finishing.doctype.dyeing_energy_allocation.dyeing_energy_allocation import ENERGY_COST_ELEMENTS
from dyeing_finishing.dyeing_finishing.doctype.production_exception_disposition.production_exception_disposition import (
	approved_dispositions, disposition_gaps,
)


SCOPE_NOTE = "材料取已提交出库库存账金额，能源取已提交分摊测算金额，人工及机台按已提交生产实绩的实际工时和生效费率标准测算；包装按实际入库重量、间接费用按批次及生效费率标准测算。零价材料和能源可凭依据人工补价，不改库存账。已审核异常处置只对既有来源行分类，异常成本已含在合计中；预计追加成本及独立回修卡不计入合计。能源、人工、机台、包装及间接费用为生产成本测算，不代表财务实际发生额；委外费用尚未接入。本单不生成库存或财务凭证。"


def _money(value):
	return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _cost_element(name, company):
	if name and frappe.db.get_value("Dyeing Cost Element", name, "company") == company:
		return name
	return None


def _stock_rows(card, source_doctype, link_field, category):
	rows = []
	missing = []
	issues = frappe.get_all(
		source_doctype,
		filters={link_field: card.name, "docstatus": 1},
		fields=["name", "stock_entry"],
		order_by="name asc",
	)
	for issue in issues:
		material_categories = {}
		if source_doctype == "Site Dyeing Material Issue":
			material_categories = {
				row.item_code: row.material_category
				for row in frappe.get_all(
					"Site Dyeing Material Issue Item",
					filters={"parent": issue.name},
					fields=["item_code", "material_category"],
				)
			}
		if not issue.stock_entry or frappe.db.get_value("Stock Entry", issue.stock_entry, "docstatus") != 1:
			missing.append(_("{0} {1} 缺少已提交的库存凭证").format(source_doctype, issue.name))
			continue
		entry = frappe.get_doc("Stock Entry", issue.stock_entry)
		if entry.company != card.company:
			frappe.throw(_("库存凭证 {0} 的公司与流转卡不一致").format(entry.name))
		ledger = frappe.get_all(
			"Stock Ledger Entry",
			filters={"voucher_type": "Stock Entry", "voucher_no": entry.name, "is_cancelled": 0, "actual_qty": ["<", 0]},
			fields=["name", "item_code", "actual_qty", "stock_uom", "stock_value_difference"],
			order_by="name asc",
		)
		if not ledger:
			missing.append(_("库存凭证 {0} 没有有效出库台账").format(entry.name))
		for sle in ledger:
			row_category = material_categories.get(sle.item_code) or category
			element = {"胚布": "CE-GREY-FABRIC", "染料": "CE-DYE", "助剂": "CE-AUXILIARY"}.get(row_category)
			customer_supplied = category == "胚布" and card.order_type == "来料加工"
			amount = Decimal(0) if customer_supplied else -_money(sle.stock_value_difference)
			if amount < 0:
				frappe.throw(_("库存台账 {0} 的出库成本异常").format(sle.name))
			status = "客户来料不计价" if customer_supplied else ("已计价" if amount > 0 else "待计价")
			rows.append({
				"cost_category": row_category,
				"cost_element": _cost_element(element, card.company),
				"source_doctype": "Stock Entry",
				"source_name": entry.name,
				"source_detail": sle.name,
				"item_code": sle.item_code,
				"description": frappe.db.get_value("Item", sle.item_code, "item_name") or sle.item_code,
				"quantity": -sle.actual_qty,
				"uom": sle.stock_uom,
				"amount": float(amount),
				"pricing_status": status,
				"remarks": _("已提交的{0} {1}；按出库库存台账金额归集").format(source_doctype, issue.name),
			})
	return rows, missing, bool(issues)


def _energy_rows(card):
	allocations = frappe.get_all(
		"Dyeing Energy Allocation",
		filters={"docstatus": 1, "company": card.company},
		pluck="name",
	)
	if not allocations:
		return []
	items = frappe.get_all(
		"Dyeing Energy Allocation Item",
		filters={"parent": ["in", allocations], "production_flow_card": card.name},
		fields=["name", "parent", "energy_type", "meter", "allocated_consumption", "uom", "estimated_amount"],
		order_by="parent asc, idx asc",
	)
	return [{
		"cost_category": item.energy_type,
		"cost_element": _cost_element(ENERGY_COST_ELEMENTS.get(item.energy_type), card.company),
		"source_doctype": "Dyeing Energy Allocation",
		"source_name": item.parent,
		"source_detail": item.name,
		"description": _("{0} - {1}").format(item.energy_type, item.meter),
		"quantity": item.allocated_consumption,
		"uom": item.uom,
		"amount": float(_money(item.estimated_amount)),
		"pricing_status": "费率测算" if _money(item.estimated_amount) > 0 else "待计价",
		"remarks": _("来源为已提交能源分摊，金额按费率测算，并非能源发票或财务实际发生额"),
	} for item in items]


def _rate_scope_score(rate, actual, work_center):
	if rate.production_resource and rate.production_resource != actual.production_resource:
		return None
	if rate.work_center and rate.work_center != work_center:
		return None
	if rate.production_operation and rate.production_operation != actual.operation:
		return None
	return (
		(4 if rate.production_resource else 0)
		+ (2 if rate.production_operation else 0)
		+ (1 if rate.work_center else 0)
	)


def _select_hourly_rate(rate_items, category, actual, work_center):
	candidates = []
	for rate in rate_items:
		if rate.cost_category != category or rate.calculation_basis != "每小时":
			continue
		score = _rate_scope_score(rate, actual, work_center)
		if score is not None:
			candidates.append((score, -(rate.idx or 0), rate))
	return max(candidates, key=lambda value: (value[0], value[1]))[2] if candidates else None


def _applicable_rate_standard(card, actual_date):
	standards = frappe.get_all(
		"Dyeing Cost Rate Standard",
		filters={
			"company": card.company,
			"docstatus": 1,
			"effective_from": ["<=", getdate(actual_date)],
		},
		fields=["name", "effective_from", "effective_to", "applicable_order_type", "creation"],
		order_by="effective_from desc, creation desc",
	)
	return next((standard for standard in standards if (
		(not standard.effective_to or getdate(standard.effective_to) >= getdate(actual_date))
		and standard.applicable_order_type in ("全部", card.order_type)
	)), None)


def _actual_cost_rows(card):
	rows = []
	missing = []
	actuals = frappe.get_all(
		"Dyeing Production Actual",
		filters={"production_flow_card": card.name, "docstatus": 1},
		fields=[
			"name", "actual_date", "production_operation_report", "operation", "operation_name",
			"production_resource", "actual_hours", "process_type",
		],
		order_by="actual_start asc, name asc",
	)
	if not actuals:
		return [], [_("尚无已提交的染色生产实绩，不能归集人工和机台成本")]

	rate_cache = {}
	for actual in actuals:
		hours = Decimal(str(actual.actual_hours or 0))
		if hours <= 0:
			missing.append(_("染色生产实绩 {0} 缺少有效实际工时").format(actual.name))
			continue
		standard = _applicable_rate_standard(card, actual.actual_date)
		if not standard:
			missing.append(_("染色生产实绩 {0} 没有适用的已提交成本费率标准").format(actual.name))
			continue
		if standard.name not in rate_cache:
			rate_cache[standard.name] = frappe.get_all(
				"Dyeing Cost Rate Standard Item",
				filters={"parent": standard.name},
				fields=[
					"idx", "cost_element", "cost_category", "cost_item", "calculation_basis",
					"uom", "unit_rate", "production_operation", "work_center", "production_resource",
				],
				order_by="idx asc",
			)
		rates = rate_cache[standard.name]
		work_center = frappe.db.get_value("Production Resource", actual.production_resource, "work_center")
		employees = frappe.get_all(
			"Production Operation Report Employee",
			filters={"parent": actual.production_operation_report},
			fields=["employee", "employee_name"],
			order_by="idx asc",
		)

		labor_rate = _select_hourly_rate(rates, "人工", actual, work_center)
		if not employees:
			missing.append(_("染色生产实绩 {0} 的报工单未登记参与员工").format(actual.name))
		elif not labor_rate:
			missing.append(_("染色生产实绩 {0} 缺少适用的人工小时费率").format(actual.name))
		else:
			quantity = hours * len(employees)
			rate = Decimal(str(labor_rate.unit_rate or 0))
			names = "、".join(employee.employee_name or employee.employee for employee in employees)
			rows.append({
				"cost_category": "人工",
				"cost_element": _cost_element(labor_rate.cost_element, card.company),
				"source_doctype": "Dyeing Production Actual",
				"source_name": actual.name,
				"source_detail": f"{actual.name}:LABOR",
				"description": _("生产人工（{0}人）：{1}").format(len(employees), names),
				"quantity": float(quantity),
				"uom": labor_rate.uom or "Hour",
				"amount": float(_money(quantity * rate)),
				"pricing_status": "费率测算" if rate > 0 else "待计价",
				"remarks": _("实绩 {0}：实际工时 {1} 小时 × {2} 人 × {3} 元/人时；费率标准 {4}").format(
					actual.name, hours, len(employees), rate, standard.name,
				),
			})

		machine_rate = _select_hourly_rate(rates, "机台", actual, work_center)
		if not machine_rate:
			missing.append(_("染色生产实绩 {0} 缺少机台 {1} 的小时费率").format(actual.name, actual.production_resource))
		else:
			rate = Decimal(str(machine_rate.unit_rate or 0))
			resource_name = frappe.db.get_value("Production Resource", actual.production_resource, "resource_name")
			rows.append({
				"cost_category": "机台",
				"cost_element": _cost_element(machine_rate.cost_element, card.company),
				"source_doctype": "Dyeing Production Actual",
				"source_name": actual.name,
				"source_detail": f"{actual.name}:MACHINE",
				"description": _("机台运行：{0}").format(resource_name or actual.production_resource),
				"quantity": float(hours),
				"uom": machine_rate.uom or "Hour",
				"amount": float(_money(hours * rate)),
				"pricing_status": "费率测算" if rate > 0 else "待计价",
				"remarks": _("实绩 {0}：实际工时 {1} 小时 × {2} 元/小时；费率标准 {3}").format(
					actual.name, hours, rate, standard.name,
				),
			})
	return rows, missing


def _production_rate_rows(card, output_weight, costing_date):
	standard = _applicable_rate_standard(card, costing_date)
	if not standard:
		return [], [_("成品入库日期 {0} 没有适用的已提交成本费率标准，不能归集包装和间接费用").format(costing_date)]
	rates = frappe.get_all(
		"Dyeing Cost Rate Standard Item",
		filters={"parent": standard.name, "cost_category": ["in", ["包装", "间接费用"]]},
		fields=[
			"idx", "cost_element", "cost_category", "cost_item", "calculation_basis",
			"standard_consumption", "uom", "unit_rate", "standard_cost",
			"production_operation", "work_center", "production_resource",
		],
		order_by="idx asc",
	)
	rates = [
		rate for rate in rates
		if not rate.production_operation and not rate.work_center and not rate.production_resource
	]
	rows = []
	missing = []
	for category in ("包装", "间接费用"):
		category_rates = [rate for rate in rates if rate.cost_category == category]
		if not category_rates:
			missing.append(_("成本费率标准 {0} 缺少通用的{1}费率").format(standard.name, category))
			continue
		for rate_row in category_rates:
			consumption = Decimal(str(rate_row.standard_consumption or 0))
			unit_rate = Decimal(str(rate_row.unit_rate or 0))
			if rate_row.calculation_basis == "每公斤":
				quantity = output_weight * consumption
				amount = quantity * unit_rate
			elif rate_row.calculation_basis == "每批":
				quantity = consumption
				amount = quantity * unit_rate
			elif rate_row.calculation_basis == "固定金额":
				quantity = Decimal(1)
				amount = Decimal(str(rate_row.standard_cost or 0))
			else:
				missing.append(_("成本费率标准 {0} 的{1}第 {2} 行计费方式不适用于批次结算").format(
					standard.name, category, rate_row.idx,
				))
				continue
			rows.append({
				"cost_category": category,
				"cost_element": _cost_element(rate_row.cost_element, card.company),
				"source_doctype": "Dyeing Cost Rate Standard",
				"source_name": standard.name,
				"source_detail": f"{standard.name}:{category}:{rate_row.idx}",
				"description": rate_row.cost_item or category,
				"quantity": float(quantity),
				"uom": rate_row.uom,
				"amount": float(_money(amount)),
				"pricing_status": "费率测算" if amount > 0 else "待计价",
				"remarks": _("按成品入库重量/批次及费率标准 {0} 测算；计费方式 {1}").format(
					standard.name, rate_row.calculation_basis,
				),
			})
	return rows, missing


def _finished_receipts(flow_card):
	receipts = frappe.get_all(
		"Finished Product Packing Receipt",
		filters={"production_flow_card": flow_card, "docstatus": 1, "packing_status": "已入库"},
		fields=["name", "packing_date", "stock_entry", "total_weight"],
	)
	return [
		receipt for receipt in receipts
		if receipt.stock_entry and frappe.db.get_value("Stock Entry", receipt.stock_entry, "docstatus") == 1
	]


@frappe.whitelist()
def can_generate_from_flow_card(flow_card):
	card = frappe.get_doc("Production Flow Card", flow_card)
	card.check_permission("read")
	return (
		card.docstatus == 1
		and bool(_finished_receipts(flow_card))
		and not frappe.db.exists("Dyeing Flow Card Cost Settlement", {"production_flow_card": flow_card, "docstatus": ["<", 2]})
	)


@frappe.whitelist()
def get_flow_card_cost_settlement(flow_card):
	card = frappe.get_doc("Production Flow Card", flow_card)
	card.check_permission("read")
	existing = frappe.get_all(
		"Dyeing Flow Card Cost Settlement",
		filters={"production_flow_card": flow_card, "docstatus": ["<", 2]},
		fields=["name", "docstatus"],
		order_by="creation desc",
		limit_page_length=1,
	)
	if existing:
		return {"name": existing[0].name, "docstatus": existing[0].docstatus, "can_create": False}
	return {
		"name": None,
		"docstatus": None,
		"can_create": card.docstatus == 1 and bool(_finished_receipts(flow_card)),
	}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def available_flow_cards(doctype, txt, searchfield, start, page_len, filters):
	frappe.has_permission("Production Flow Card", ptype="read", throw=True)
	return frappe.db.sql(
		f"""
		SELECT `tabProduction Flow Card`.name
		FROM `tabProduction Flow Card`
		WHERE `tabProduction Flow Card`.docstatus = 1
			AND `tabProduction Flow Card`.name LIKE %(txt)s
			AND EXISTS (
				SELECT 1 FROM `tabFinished Product Packing Receipt` packing
				JOIN `tabStock Entry` entry ON entry.name = packing.stock_entry AND entry.docstatus = 1
				WHERE packing.production_flow_card = `tabProduction Flow Card`.name
					AND packing.docstatus = 1 AND packing.packing_status = '已入库'
			)
			AND NOT EXISTS (
				SELECT 1 FROM `tabDyeing Flow Card Cost Settlement` settlement
				WHERE settlement.production_flow_card = `tabProduction Flow Card`.name
					AND settlement.docstatus < 2
			)
			{get_match_cond("Production Flow Card")}
		ORDER BY `tabProduction Flow Card`.name DESC
		LIMIT %(page_len)s OFFSET %(start)s
		""",
		{"txt": f"%{txt}%", "start": start, "page_len": page_len},
	)


def build_snapshot(flow_card):
	card = frappe.get_doc("Production Flow Card", flow_card)
	if card.docstatus != 1:
		frappe.throw(_("只能为已审核的生产流转卡生成成本结算单"))
	rows = []
	missing = []
	for source_doctype, link_field, category in (
		("Grey Fabric Issue", "flow_card", "胚布"),
		("Site Dyeing Material Issue", "production_flow_card", "染化料"),
	):
		found, issues, has_source = _stock_rows(card, source_doctype, link_field, category)
		rows.extend(found)
		missing.extend(issues)
		if not has_source:
			missing.append(_("尚无已提交的{0}").format(source_doctype))
	energy = _energy_rows(card)
	rows.extend(energy)
	if frappe.db.count("Dyeing Production Actual", {"production_flow_card": card.name, "docstatus": 1}) and not energy:
		missing.append(_("染色生产实绩尚无已提交的能源分摊"))
	actual_costs, actual_missing = _actual_cost_rows(card)
	rows.extend(actual_costs)
	missing.extend(actual_missing)
	packing = _finished_receipts(card.name)
	output_weight = sum((Decimal(str(row.total_weight or 0)) for row in packing), Decimal(0))
	if output_weight <= 0:
		missing.append(_("尚无已提交的成品入库凭证及包装重量，不能计算单位成本"))
	else:
		costing_date = max(getdate(row.packing_date) for row in packing)
		production_rates, production_rate_missing = _production_rate_rows(card, output_weight, costing_date)
		rows.extend(production_rates)
		missing.extend(production_rate_missing)
	return card, rows, missing, output_weight


def _apply_manual_prices(rows, previous):
	for row in rows:
		price = previous.get((row["source_name"], row["source_detail"]))
		if not price or row["pricing_status"] != "待计价":
			continue
		rate, basis = price
		if Decimal(str(rate or 0)) < 0:
			frappe.throw(_("人工补录单价不能小于零"))
		if not rate:
			continue
		if row["source_doctype"] not in ("Stock Entry", "Dyeing Energy Allocation") or not (basis or "").strip():
			frappe.throw(_("人工补录价格必须填写来源依据"))
		row["manual_unit_rate"] = float(rate)
		row["manual_price_basis"] = basis
		row["amount"] = float(_money(Decimal(str(row["quantity"])) * Decimal(str(rate))))
		row["pricing_status"] = "人工补录"
		row["remarks"] += (_("；本行金额按人工补录单价计算，不等于库存台账金额") if row["source_doctype"] == "Stock Entry" else _("；本行金额按人工补录单价计算，并非能源发票实际金额"))


def _classify_exception_cost(rows, dispositions):
	material_entries = {}
	energy_allocations = {}
	production_actuals = {}
	for disposition in dispositions:
		if getattr(disposition, "material_issue", None):
			entry = frappe.db.get_value("Site Dyeing Material Issue", disposition.material_issue, "stock_entry")
			if entry:
				material_entries[entry] = disposition.name
		if getattr(disposition, "energy_allocation", None):
			energy_allocations[disposition.energy_allocation] = disposition.name
		if getattr(disposition, "dyeing_production_actual", None):
			production_actuals[disposition.dyeing_production_actual] = disposition.name
	for row in rows:
		source_map = {
			"Stock Entry": material_entries,
			"Dyeing Energy Allocation": energy_allocations,
			"Dyeing Production Actual": production_actuals,
		}.get(row["source_doctype"], {})
		name = source_map.get(row["source_name"])
		row["cost_bucket"] = "异常" if name else "正常"
		row["exception_disposition"] = name


class DyeingFlowCardCostSettlement(Document):
	def before_insert(self):
		self.settlement_no = self.name
		self.settlement_status = "草稿"

	def validate(self):
		if self.is_new():
			frappe.db.sql("SELECT name FROM `tabProduction Flow Card` WHERE name = %s FOR UPDATE", self.production_flow_card)
		filters = {"production_flow_card": self.production_flow_card, "docstatus": ["<", 2]}
		if self.name:
			filters["name"] = ["!=", self.name]
		if existing := frappe.db.exists("Dyeing Flow Card Cost Settlement", filters):
			frappe.throw(_("流转卡 {0} 已有成本结算单 {1}，不能重复保存").format(self.production_flow_card, existing))
		self.settlement_no = self.name
		self.settlement_date = self.settlement_date or nowdate()
		previous = {
			(row.source_name, row.source_detail): (row.manual_unit_rate, row.manual_price_basis)
			for row in self.items
		}
		card, rows, missing, output_weight = build_snapshot(self.production_flow_card)
		_apply_manual_prices(rows, previous)
		dispositions = approved_dispositions(self.production_flow_card)
		_classify_exception_cost(rows, dispositions)
		missing.extend(disposition_gaps(self.production_flow_card, dispositions))
		self.company = card.company
		self.currency = frappe.db.get_value("Company", card.company, "default_currency")
		self.sales_order = card.sales_order
		self.customer_name = frappe.db.get_value("Customer", card.customer, "customer_name") or card.customer
		self.order_type = card.order_type
		self.output_weight = float(output_weight)
		self.last_calculated_at = now_datetime()
		self.scope_note = SCOPE_NOTE
		self.set("items", [])
		for row in rows:
			self.append("items", row)
		self.set("exceptions", [])
		for row in dispositions:
			self.append("exceptions", {
				"disposition": row.name, "exception_type": row.exception_type,
				"production_operation_report": row.production_operation_report,
				"dyeing_production_actual": row.dyeing_production_actual,
				"affected_qty": row.affected_qty, "decision": row.decision,
				"impact_scope": row.impact_scope, "trace_summary": row.trace_summary,
				"batch_no": row.batch_no, "roll_no": row.roll_no,
				"cost_bearer": row.cost_bearer, "material_issue": row.material_issue,
				"energy_allocation": row.energy_allocation,
				"rework_flow_card": row.rework_flow_card,
				"estimated_extra_cost": row.estimated_extra_cost,
				"reviewed_by": row.reviewed_by, "reviewed_at": row.reviewed_at,
				"reason": row.reason,
			})
		self.material_cost = float(sum((_money(row["amount"]) for row in rows if row["source_doctype"] == "Stock Entry"), Decimal(0)))
		self.energy_cost = float(sum((_money(row["amount"]) for row in rows if row["source_doctype"] == "Dyeing Energy Allocation"), Decimal(0)))
		self.labor_cost = float(sum((_money(row["amount"]) for row in rows if row["cost_category"] == "人工"), Decimal(0)))
		self.machine_cost = float(sum((_money(row["amount"]) for row in rows if row["cost_category"] == "机台"), Decimal(0)))
		self.packaging_cost = float(sum((_money(row["amount"]) for row in rows if row["cost_category"] == "包装"), Decimal(0)))
		self.overhead_cost = float(sum((_money(row["amount"]) for row in rows if row["cost_category"] == "间接费用"), Decimal(0)))
		self.total_cost = float(
			_money(self.material_cost) + _money(self.energy_cost) + _money(self.labor_cost)
			+ _money(self.machine_cost) + _money(self.packaging_cost) + _money(self.overhead_cost)
		)
		self.exception_cost = float(sum((_money(row["amount"]) for row in rows if row["cost_bucket"] == "异常"), Decimal(0)))
		self.normal_cost = float(_money(self.total_cost) - _money(self.exception_cost))
		self.exception_count = len(dispositions)
		self.estimated_extra_cost = float(sum((_money(row.estimated_extra_cost) for row in dispositions), Decimal(0)))
		self.unit_cost = float((_money(self.total_cost) / output_weight).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)) if output_weight > 0 else 0
		self.unvalued_count = sum(row["pricing_status"] == "待计价" for row in rows)
		self.manual_price_count = sum(row["pricing_status"] == "人工补录" for row in rows)
		self.manual_price_amount = float(sum((_money(row["amount"]) for row in rows if row["pricing_status"] == "人工补录"), Decimal(0)))
		self.missing_sources = "\n".join(missing)
		if self.docstatus == 0:
			self.settlement_status = "草稿"

	def before_submit(self):
		frappe.db.sql("SELECT name FROM `tabProduction Flow Card` WHERE name = %s FOR UPDATE", self.production_flow_card)
		if frappe.db.exists("Dyeing Flow Card Cost Settlement", {
			"production_flow_card": self.production_flow_card, "docstatus": 1, "name": ["!=", self.name],
		}):
			frappe.throw(_("此流转卡已有已确认的成本结算单"))
		self.validate()
		if not self.items or self.missing_sources or self.unvalued_count:
			frappe.throw(_("来源不完整或存在待计价行，暂不能确认结算；请查看待补来源和明细"))
		if self.manual_price_count and not ({"Accounts Manager", "System Manager"} & set(frappe.get_roles())):
			frappe.throw(_("包含人工补录价格的结算单须由财务经理或系统经理确认"))
		self.settlement_status = "已确认"

	def on_cancel(self):
		self.db_set("settlement_status", "已取消", update_modified=False)


@frappe.whitelist()
def create_from_flow_card(flow_card):
	frappe.has_permission("Dyeing Flow Card Cost Settlement", ptype="create", throw=True)
	card = frappe.get_doc("Production Flow Card", flow_card)
	card.check_permission("read")
	if card.docstatus != 1:
		frappe.throw(_("请先审核生产流转卡"))
	frappe.db.sql("SELECT name FROM `tabProduction Flow Card` WHERE name = %s FOR UPDATE", flow_card)
	if not _finished_receipts(flow_card):
		frappe.throw(_("请先提交成品包装入库单及其库存凭证，再生成成本结算单"))
	existing = frappe.get_all(
		"Dyeing Flow Card Cost Settlement",
		filters={"production_flow_card": flow_card, "docstatus": ["<", 2]},
		fields=["name", "docstatus"], order_by="creation desc", limit_page_length=1,
	)
	if existing:
		if existing[0].docstatus == 0:
			draft = frappe.get_doc("Dyeing Flow Card Cost Settlement", existing[0].name)
			draft.check_permission("write")
			draft.save()
		return existing[0].name
	doc = frappe.get_doc({"doctype": "Dyeing Flow Card Cost Settlement", "production_flow_card": flow_card, "settlement_date": getdate(nowdate())})
	doc.insert()
	return doc.name


@frappe.whitelist()
def set_manual_price(settlement, item_code, rate, basis):
	doc = frappe.get_doc("Dyeing Flow Card Cost Settlement", settlement)
	doc.check_permission("write")
	if doc.docstatus != 0:
		frappe.throw(_("只能在草稿结算单中补录价格"))
	rate = Decimal(str(rate or 0))
	if rate <= 0 or not (basis or "").strip():
		frappe.throw(_("请填写大于零的单价及补录依据"))
	matched = [row for row in doc.items if row.item_code == item_code and row.source_doctype == "Stock Entry" and row.pricing_status in ("待计价", "人工补录")]
	if not matched:
		frappe.throw(_("该物料没有可补录的零估值出库明细"))
	if any(row.uom != "Kg" for row in matched):
		frappe.throw(_("所提供的元/Kg 单价只能用于 Kg 明细"))
	for row in matched:
		row.manual_unit_rate = float(rate)
		row.manual_price_basis = basis.strip()
	doc.save()
	return {"name": doc.name, "manual_price_amount": doc.manual_price_amount, "unvalued_count": doc.unvalued_count}


@frappe.whitelist()
def set_energy_price(settlement, source_detail, rate, basis):
	doc = frappe.get_doc("Dyeing Flow Card Cost Settlement", settlement)
	doc.check_permission("write")
	if doc.docstatus != 0:
		frappe.throw(_("只能在草稿结算单中补录价格"))
	rate = Decimal(str(rate or 0))
	if rate <= 0 or not (basis or "").strip():
		frappe.throw(_("请填写大于零的单价及补录依据"))
	matched = [row for row in doc.items if row.source_detail == source_detail and row.source_doctype == "Dyeing Energy Allocation" and row.pricing_status in ("待计价", "人工补录")]
	if len(matched) != 1:
		frappe.throw(_("未找到可补价的已提交能源分摊明细"))
	matched[0].manual_unit_rate = float(rate)
	matched[0].manual_price_basis = basis.strip()
	doc.save()
	return {"name": doc.name, "energy_cost": doc.energy_cost, "unvalued_count": doc.unvalued_count}


def sync_cost_settlement(flow_card, create=False):
	if not flow_card or not frappe.db.exists("DocType", "Dyeing Flow Card Cost Settlement"):
		return None
	if frappe.db.get_value("Production Flow Card", flow_card, "docstatus") != 1:
		return None
	frappe.db.sql("SELECT name FROM `tabProduction Flow Card` WHERE name = %s FOR UPDATE", flow_card)
	active = frappe.get_all(
		"Dyeing Flow Card Cost Settlement",
		filters={"production_flow_card": flow_card, "docstatus": ["<", 2]},
		fields=["name", "docstatus"], order_by="docstatus desc, creation desc", limit_page_length=1,
	)
	if active:
		if active[0].docstatus == 0:
			frappe.get_doc("Dyeing Flow Card Cost Settlement", active[0].name).save(ignore_permissions=True)
		return active[0].name
	if not create:
		return None
	doc = frappe.get_doc({"doctype": "Dyeing Flow Card Cost Settlement", "production_flow_card": flow_card, "settlement_date": getdate(nowdate())})
	doc.insert(ignore_permissions=True)
	return doc.name


def _source_flow_cards(doc):
	if doc.doctype == "Dyeing Energy Allocation":
		return {row.production_flow_card for row in doc.items if row.production_flow_card}
	if doc.doctype == "Stock Entry" and doc.get("custom_finished_packing_receipt"):
		flow_card = frappe.db.get_value("Finished Product Packing Receipt", doc.custom_finished_packing_receipt, "production_flow_card")
		return {flow_card} if flow_card else set()
	field = "flow_card" if doc.doctype == "Grey Fabric Issue" else "production_flow_card"
	return {doc.get(field)} if doc.get(field) else set()


def guard_confirmed_settlement_source(doc, method=None):
	if doc.doctype == "Dyeing Cost Rate Standard":
		settlements = frappe.get_all(
			"Dyeing Flow Card Cost Settlement Item",
			filters={"source_doctype": doc.doctype, "source_name": doc.name},
			pluck="parent",
		)
		for settlement in set(settlements):
			if frappe.db.get_value("Dyeing Flow Card Cost Settlement", settlement, "docstatus") == 1:
				frappe.throw(_("成本费率标准已用于已确认的成本结算单 {0}，请先取消结算").format(settlement))
		return
	if doc.doctype == "Stock Entry":
		items = frappe.get_all(
			"Dyeing Flow Card Cost Settlement Item",
			filters={"source_doctype": "Stock Entry", "source_name": doc.name},
			pluck="parent",
		)
		for name in set(items):
			if frappe.db.get_value("Dyeing Flow Card Cost Settlement", name, "docstatus") == 1:
				frappe.throw(_("库存凭证已用于已确认的成本结算单 {0}，请先取消结算").format(name))
		if not doc.get("custom_finished_packing_receipt"):
			return
	for flow_card in _source_flow_cards(doc):
		name = frappe.db.exists("Dyeing Flow Card Cost Settlement", {"production_flow_card": flow_card, "docstatus": 1})
		if name:
			frappe.throw(_("流转卡 {0} 已有已确认的成本结算单 {1}，请先取消结算").format(flow_card, name))


def sync_settlement_from_source(doc, method=None):
	create = doc.doctype == "Finished Product Packing Receipt" and method == "on_submit"
	for flow_card in _source_flow_cards(doc):
		savepoint = "cost_sync_" + frappe.generate_hash(length=10)
		frappe.db.savepoint(savepoint)
		try:
			sync_cost_settlement(flow_card, create=create)
		except Exception:
			frappe.db.rollback(save_point=savepoint)
			frappe.log_error(title=_("流转卡成本自动归集失败：{0}").format(flow_card), message=frappe.get_traceback())
