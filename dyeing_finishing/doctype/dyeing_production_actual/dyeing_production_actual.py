import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, getdate, nowdate, time_diff_in_hours


class DyeingProductionActual(Document):
	def before_insert(self):
		self.actual_no = self.name
		self.actual_date = self.actual_date or nowdate()
		self.actual_status = "草稿"

	def validate(self):
		self.actual_no = self.name
		self.actual_date = self.actual_date or nowdate()
		self._copy_report_snapshot()
		self._validate_times(require_complete=self.docstatus == 1)
		self._validate_stages(require_complete=self.docstatus == 1)
		if self.docstatus == 0:
			self.actual_status = "草稿"

	def before_submit(self):
		self._check_report_available()
		self._validate_times(require_complete=True)
		self._validate_stages(require_complete=True)
		frappe.db.sql(
			"SELECT name FROM `tabProduction Operation Report` WHERE name = %s FOR UPDATE",
			self.production_operation_report,
		)
		if frappe.db.exists("Dyeing Production Actual", {
			"production_operation_report": self.production_operation_report,
			"docstatus": 1,
			"name": ["!=", self.name],
		}):
			frappe.throw(_("此报工单已有已提交的染色生产实绩单"))
		self.actual_status = "已提交"

	def on_cancel(self):
		self.db_set("actual_status", "已取消", update_modified=False)

	def before_cancel(self):
		if not frappe.db.exists("DocType", "Dyeing Energy Allocation Item"):
			return
		frappe.db.sql("SELECT name FROM `tabDyeing Production Actual` WHERE name = %s FOR UPDATE", self.name)
		allocation = frappe.db.sql("""
			SELECT parent.name FROM `tabDyeing Energy Allocation Item` item
			JOIN `tabDyeing Energy Allocation` parent ON parent.name = item.parent
			WHERE item.production_actual = %s AND parent.docstatus = 1 LIMIT 1
		""", self.name)
		if allocation:
			frappe.throw(_("此实绩单已用于生产能源分摊单 {0}，请先取消分摊单").format(allocation[0][0]))

	def _check_report_available(self):
		if not self.production_operation_report:
			frappe.throw(_("请选择已提交的工序报工单"))
		report = frappe.get_doc("Production Operation Report", self.production_operation_report)
		if report.docstatus != 1:
			frappe.throw(_("只能引用已提交的工序报工单"))
		if (report.operation_name or "").strip() != "染色":
			frappe.throw(_("染色生产实绩单只能引用染色工序报工单"))
		return report

	def _copy_report_snapshot(self):
		report = self._check_report_available()
		card = frappe.get_doc("Production Flow Card", report.production_flow_card)
		self.production_flow_card = card.name
		self.vat_no = card.flow_card_no or card.name
		self.customer = card.customer
		self.customer_name = frappe.db.get_value("Customer", card.customer, "customer_name") or card.customer
		self.operation = report.operation
		self.operation_name = report.operation_name
		self.production_resource = report.production_resource or self.production_resource
		self.resource_name = (
			frappe.db.get_value("Production Resource", self.production_resource, "resource_name")
			if self.production_resource else ""
		)
		self.completed_qty = report.completed_qty
		self.loss_qty = report.loss_qty
		self.defective_qty = report.defective_qty
		self.rework_qty = report.rework_qty
		self.uom = report.uom
		self.employee_names = "、".join(row.employee_name or row.employee for row in report.employees)
		self.company = card.company or frappe.defaults.get_user_default("Company")

	def _validate_times(self, require_complete=False):
		if not self.actual_start or not self.actual_end:
			self.actual_hours = 0
			if require_complete:
				frappe.throw(_("请填写实际开始和结束时间"))
			return
		if get_datetime(self.actual_end) <= get_datetime(self.actual_start):
			frappe.throw(_("实际结束时间必须晚于开始时间"))
		self.actual_hours = flt(time_diff_in_hours(self.actual_end, self.actual_start), 3)
		if not self.production_resource:
			frappe.throw(_("报工单缺少生产机台，请先补齐报工资料"))

	def _validate_stages(self, require_complete=False):
		if not self.stages:
			if require_complete:
				frappe.throw(_("请至少填写一个工艺阶段"))
			return
		previous_end = None
		for row in self.stages:
			if not row.stage_name or not row.actual_start or not row.actual_end:
				frappe.throw(_("第 {0} 行请填写阶段名称及起止时间").format(row.idx))
			start, end = get_datetime(row.actual_start), get_datetime(row.actual_end)
			if start < get_datetime(self.actual_start) or end > get_datetime(self.actual_end) or end <= start:
				frappe.throw(_("第 {0} 行阶段时间须落在本单实际起止时间内").format(row.idx))
			if previous_end and start < previous_end:
				frappe.throw(_("第 {0} 行工艺阶段与前一阶段时间重叠").format(row.idx))
			if row.actual_temperature is not None and flt(row.actual_temperature) < 0:
				frappe.throw(_("第 {0} 行实际温度不能小于零").format(row.idx))
			row.duration_minutes = flt((end - start).total_seconds() / 60, 1)
			previous_end = end


def ensure_dyeing_production_actual(report):
	if isinstance(report, str):
		report = frappe.get_doc("Production Operation Report", report)
	if report.docstatus != 1 or (report.operation_name or "").strip() != "染色":
		return None
	existing = frappe.get_all(
		"Dyeing Production Actual",
		filters={"production_operation_report": report.name, "docstatus": ["<", 2]},
		fields=["name"],
		order_by="creation desc",
		limit_page_length=1,
	)
	if existing:
		return existing[0].name
	doc = frappe.get_doc({
		"doctype": "Dyeing Production Actual",
		"actual_date": getdate(report.report_time),
		"production_operation_report": report.name,
		"process_type": "正常",
		"remarks": _("由染色工序报工单 {0} 自动建立，请补充实际时间和工艺阶段后提交。").format(report.name),
	})
	doc.insert(ignore_permissions=True)
	return doc.name
