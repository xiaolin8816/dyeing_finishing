import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, nowdate


QUANTITY_FIELDS = {"损耗": "loss_qty", "次品": "defective_qty", "返修": "rework_qty"}
TOLERANCE = 0.000001


def _card_batches(card):
	return sorted({row.batch_no for row in card.grey_fabric_issues if row.batch_no})


@frappe.whitelist()
def get_flow_card_batches(flow_card):
	card = frappe.get_doc("Production Flow Card", flow_card)
	card.check_permission("read")
	return _card_batches(card)


def approved_dispositions(flow_card):
	return frappe.get_all(
		"Production Exception Disposition",
		filters={"production_flow_card": flow_card, "docstatus": 1},
		fields=["name", "production_operation_report", "dyeing_production_actual", "exception_type", "affected_qty", "impact_scope", "batch_no", "roll_no", "trace_summary", "decision", "reason", "cost_bearer", "material_issue", "energy_allocation", "rework_flow_card", "estimated_extra_cost", "reviewed_by", "reviewed_at"],
		order_by="name asc",
	)


def disposition_gaps(flow_card, approved=None):
	approved = approved if approved is not None else approved_dispositions(flow_card)
	covered = {}
	covered_actuals = set()
	for row in approved:
		key = (row.production_operation_report, row.exception_type)
		covered[key] = covered.get(key, 0) + flt(row.affected_qty)
		if row.dyeing_production_actual:
			covered_actuals.add(row.dyeing_production_actual)
	gaps = []
	for report in frappe.get_all("Production Operation Report", filters={"production_flow_card": flow_card, "docstatus": 1}, fields=["name", *QUANTITY_FIELDS.values()]):
		for kind, field in QUANTITY_FIELDS.items():
			if flt(report.get(field)) - covered.get((report.name, kind), 0) > TOLERANCE:
				gaps.append(_("报工单 {0} 的{1}尚未全部审核处置").format(report.name, kind))
	for actual in frappe.get_all("Dyeing Production Actual", filters={"production_flow_card": flow_card, "docstatus": 1}, fields=["name", "process_type", "exception_description", "additional_treatment"]):
		if (actual.process_type != "正常" or (actual.exception_description or "").strip() or (actual.additional_treatment or "").strip()) and actual.name not in covered_actuals:
			gaps.append(_("染色实绩单 {0} 的异常或追加处理尚未审核处置").format(actual.name))
	if frappe.db.exists("Production Exception Disposition", {"production_flow_card": flow_card, "docstatus": 0}):
		gaps.append(_("存在尚未审核的生产异常处置单"))
	return gaps


class ProductionExceptionDisposition(Document):
	def before_insert(self):
		self.disposition_no = self.name
		self.disposition_status = "草稿"

	def validate(self):
		self.disposition_no = self.name
		self.disposition_date = self.disposition_date or nowdate()
		if self.docstatus == 0:
			self.disposition_status = "草稿"
		report = frappe.get_doc("Production Operation Report", self.production_operation_report)
		if report.docstatus != 1 or report.production_flow_card != self.production_flow_card:
			frappe.throw(_("只能引用本流转卡已提交的工序报工单"))
		card = frappe.get_doc("Production Flow Card", self.production_flow_card)
		if card.docstatus != 1:
			frappe.throw(_("生产流转卡必须已审核"))
		self.company = card.company
		self.uom = report.uom
		self._validate_affected_scope(card)
		if self.dyeing_production_actual:
			actual = frappe.get_doc("Dyeing Production Actual", self.dyeing_production_actual)
			if actual.docstatus != 1 or actual.production_operation_report != report.name or actual.production_flow_card != card.name:
				frappe.throw(_("染色实绩单必须是此报工单自动关联的已提交实绩"))
		if self.exception_type in QUANTITY_FIELDS:
			limit = flt(report.get(QUANTITY_FIELDS[self.exception_type]))
			if flt(self.affected_qty) <= 0 or flt(self.affected_qty) - limit > TOLERANCE:
				frappe.throw(_("影响数量必须大于零且不能超过报工单对应异常数量 {0}").format(limit))
		else:
			processed = sum(flt(report.get(field)) for field in ("completed_qty", *QUANTITY_FIELDS.values()))
			if not self.dyeing_production_actual or flt(self.affected_qty) < 0 or flt(self.affected_qty) - processed > TOLERANCE:
				frappe.throw(_("工艺异常必须关联已提交染色实绩，影响数量须在零至本次处理量之间"))
			if not (actual.process_type != "正常" or (actual.exception_description or "").strip() or (actual.additional_treatment or "").strip()):
				frappe.throw(_("所选实绩单没有记录工艺异常"))
		if flt(self.estimated_extra_cost) < 0:
			frappe.throw(_("预计追加成本不能小于零"))
		self._validate_cost_sources(card)

	def _validate_affected_scope(self, card):
		batches = _card_batches(card)
		rows = self.get("affected_items") or []
		self.roll_no = (self.roll_no or "").strip()
		if self.impact_scope == "整卡/整缸":
			if rows or self.roll_no or (self.batch_no and (len(batches) != 1 or self.batch_no != batches[0])):
				frappe.throw(_("整卡/整缸异常不能指定部分批次或匹号"))
			self.batch_no = batches[0] if len(batches) == 1 else None
			self.trace_summary = _("整卡/整缸") + (f"：{self.batch_no}" if self.batch_no else "")
		elif self.impact_scope == "指定批次":
			if self.batch_no not in batches or self.roll_no or rows:
				frappe.throw(_("指定批次时须选择此流转卡的一个批次，且不能填写匹号或多批次明细"))
			self.trace_summary = self.batch_no
		elif self.impact_scope == "指定匹号":
			if self.batch_no not in batches or not self.roll_no or rows:
				frappe.throw(_("指定匹号时须选择此流转卡的批次并填写现场确认的匹号"))
			self.trace_summary = f"{self.batch_no} / {self.roll_no}"
		elif self.impact_scope == "多个批次/匹号":
			if self.batch_no or self.roll_no or len(rows) < 2:
				frappe.throw(_("多批次/匹号异常须填写至少两条明细，且不能填写单一批次或匹号"))
			seen = set()
			whole_batches = set()
			for row in rows:
				row.roll_no = (row.roll_no or "").strip()
				if row.batch_no not in batches:
					frappe.throw(_("第 {0} 行批次不属于此流转卡").format(row.idx))
				key = (row.batch_no, row.roll_no)
				if key in seen:
					frappe.throw(_("受影响批次/匹号不能重复"))
				seen.add(key)
				if not row.roll_no:
					whole_batches.add(row.batch_no)
			if any(batch in whole_batches and roll for batch, roll in seen):
				frappe.throw(_("同一批次不能同时填写整批和单匹，避免重复归属"))
			self.trace_summary = "、".join(f"{batch}/{roll}" if roll else batch for batch, roll in sorted(seen))
		else:
			frappe.throw(_("请选择影响范围"))

	def _validate_cost_sources(self, card):
		if self.material_issue:
			issue = frappe.get_doc("Site Dyeing Material Issue", self.material_issue)
			if issue.docstatus != 1 or issue.production_flow_card != card.name or not issue.stock_entry or frappe.db.get_value("Stock Entry", issue.stock_entry, "docstatus") != 1:
				frappe.throw(_("异常领料单必须属于本流转卡且已有已提交库存凭证"))
		if self.energy_allocation:
			allocation = frappe.get_doc("Dyeing Energy Allocation", self.energy_allocation)
			if allocation.docstatus != 1 or allocation.company != card.company:
				frappe.throw(_("异常能源分摊单必须已提交且公司一致"))
			items = [row for row in allocation.items if row.production_flow_card == card.name]
			if len(items) != 1:
				frappe.throw(_("异常能源分摊单中本流转卡必须恰有一条明细，避免将正常能源误归为异常"))
		if self.rework_flow_card:
			rework = frappe.get_doc("Production Flow Card", self.rework_flow_card)
			if rework.name == card.name or rework.original_flow_card != card.name or rework.company != card.company:
				frappe.throw(_("回修流转卡必须是本流转卡的独立回修卡"))

	def before_submit(self):
		frappe.db.sql("SELECT name FROM `tabProduction Flow Card` WHERE name = %s FOR UPDATE", self.production_flow_card)
		settlement = frappe.db.exists("Dyeing Flow Card Cost Settlement", {"production_flow_card": self.production_flow_card, "docstatus": 1})
		if settlement:
			frappe.throw(_("流转卡已有已确认成本结算单 {0}，请先取消结算").format(settlement))
		frappe.db.sql("SELECT name FROM `tabProduction Operation Report` WHERE name = %s FOR UPDATE", self.production_operation_report)
		self.validate()
		if self.exception_type in QUANTITY_FIELDS:
			other = frappe.get_all("Production Exception Disposition", filters={
				"production_operation_report": self.production_operation_report, "exception_type": self.exception_type,
				"docstatus": 1, "name": ["!=", self.name],
			}, pluck="affected_qty")
			limit = flt(frappe.db.get_value("Production Operation Report", self.production_operation_report, QUANTITY_FIELDS[self.exception_type]))
			if sum(flt(qty) for qty in other) + flt(self.affected_qty) - limit > TOLERANCE:
				frappe.throw(_("已审核处置数量不能超过报工单异常数量"))
		if self.cost_bearer == "待判定" or self.responsible_party == "待判定":
			frappe.throw(_("审核前须明确责任方及成本承担方"))
		if self.material_issue or self.energy_allocation:
			for other in approved_dispositions(self.production_flow_card):
				if other.name != self.name and ((self.material_issue and other.material_issue == self.material_issue) or (self.energy_allocation and other.energy_allocation == self.energy_allocation)):
					frappe.throw(_("同一异常成本凭据不能重复关联已审核处置单 {0}").format(other.name))
		self.reviewed_by = frappe.session.user
		self.reviewed_at = now_datetime()
		self.disposition_status = "已审核"

	def before_cancel(self):
		frappe.db.sql("SELECT name FROM `tabProduction Flow Card` WHERE name = %s FOR UPDATE", self.production_flow_card)
		name = frappe.db.exists("Dyeing Flow Card Cost Settlement", {"production_flow_card": self.production_flow_card, "docstatus": 1})
		if name:
			frappe.throw(_("处置结果已用于已确认的成本结算单 {0}，请先取消结算").format(name))

	def on_cancel(self):
		self.db_set("disposition_status", "已取消", update_modified=False)
		self._sync_settlement()

	def on_submit(self):
		self._sync_settlement()

	def _sync_settlement(self):
		from dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement import sync_cost_settlement
		sync_cost_settlement(self.production_flow_card, create=False)


def guard_disposition_source(doc, method=None):
	field = {
		"Production Operation Report": "production_operation_report",
		"Dyeing Production Actual": "dyeing_production_actual",
		"Site Dyeing Material Issue": "material_issue",
		"Dyeing Energy Allocation": "energy_allocation",
	}.get(doc.doctype)
	if not field:
		return
	name = frappe.db.exists("Production Exception Disposition", {field: doc.name, "docstatus": 1})
	if name:
		frappe.throw(_("来源单据已被已审核处置单 {0} 引用，请先取消处置单").format(name))


def guard_disposition_stock_entry(doc, method=None):
	issues = frappe.get_all("Site Dyeing Material Issue", filters={"stock_entry": doc.name, "docstatus": 1}, pluck="name")
	if not issues:
		return
	name = frappe.db.exists("Production Exception Disposition", {"material_issue": ["in", issues], "docstatus": 1})
	if name:
		frappe.throw(_("库存凭证已被已审核异常处置单 {0} 引用，请先取消处置单").format(name))
