import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, nowdate

from dyeing_finishing.dyeing_finishing.doctype.production_flow_card.production_flow_card import (
	ensure_flow_card_open,
	record_production_progress,
	remove_production_progress,
)

TOLERANCE = 0.000001


class ProductionOperationReport(Document):
	def before_insert(self):
		self.report_no = self.name
		self.report_time = self.report_time or now_datetime()
		self.report_status = "保存"

	def validate(self):
		self.report_no = self.name
		self.report_time = self.report_time or now_datetime()
		self._set_task_details()
		self._validate_employees()
		self._set_quantities()

	def before_submit(self):
		self.report_status = "已完成" if flt(self.pending_qty) <= TOLERANCE else "部分完成"

	def on_submit(self):
		_refresh_operation(self.production_flow_card, self.operation_row)
		status = f"{self.operation_name}{'已完成' if self.report_status == '已完成' else '部分完成'}"
		record_production_progress(
			self.production_flow_card,
			self.operation_name,
			status,
			"Production Operation Report",
			self.name,
			quantity=self.completed_qty,
			uom=self.uom,
			production_resource=self.production_resource,
			description=_("生产工序报工：{0}；合格 {1} {2}").format(
				self.operation_name, self.completed_qty, self.uom or ""
			),
		)

	def on_cancel(self):
		self.db_set("report_status", "已取消", update_modified=False)
		remove_production_progress("Production Operation Report", self.name)
		_refresh_operation(self.production_flow_card, self.operation_row)

	def _set_task_details(self):
		if not self.production_flow_card or not self.operation_row:
			frappe.throw(_("请选择生产流转卡和生产工序"))
		card = frappe.get_doc("Production Flow Card", self.production_flow_card)
		ensure_flow_card_open(card)
		row = next((item for item in card.operations if item.name == self.operation_row), None)
		if not row:
			frappe.throw(_("所选工序不属于生产流转卡 {0}").format(card.name))
		self.operation = row.operation
		self.operation_name = row.operation_name or frappe.db.get_value(
			"Production Operation", row.operation, "production_operation_name"
		) or row.operation
		self.sequence_no = row.idx
		self.operation_total = len(card.operations)
		self.production_resource = self.production_resource or row.production_resource
		self.resource_name = (
			frappe.db.get_value("Production Resource", self.production_resource, "resource_name")
			if self.production_resource else ""
		)
		self.uom = card.finished_uom or "Kg"
		missing = [
			item.operation_name or item.operation
			for item in card.operations
			if item.idx < row.idx and item.operation_status != "已完成"
		]
		self.has_missing_previous = 1 if missing else 0
		self.missing_previous_operations = "、".join(missing)

	def _validate_employees(self):
		if not self.employees:
			frappe.throw(_("请至少扫描一名员工"))
		seen = set()
		primary = []
		for row in self.employees:
			if not row.employee or row.employee in seen:
				frappe.throw(_("参与员工不能为空或重复"))
			seen.add(row.employee)
			employee = frappe.db.get_value("Employee", row.employee, ["employee_name", "status"], as_dict=True)
			if not employee or employee.status != "Active":
				frappe.throw(_("员工 {0} 不存在或不是在职状态").format(row.employee))
			row.employee_name = employee.employee_name
			row.scanned_at = row.scanned_at or now_datetime()
			if row.worker_role == "主操作员":
				primary.append(row.employee)
		if len(primary) != 1:
			frappe.throw(_("必须且只能有一名主操作员"))
		if not _employee_can_operate(primary[0], self.operation):
			frappe.throw(_("主操作员没有工序“{0}”的操作权限").format(self.operation_name))

	def _set_quantities(self):
		available = _available_quantity(self.production_flow_card, self.operation_row, self.name)
		self.available_qty = available
		values = [self.completed_qty, self.loss_qty, self.defective_qty, self.rework_qty]
		if any(flt(value) < 0 for value in values):
			frappe.throw(_("报工数量不能小于零"))
		processed = sum(flt(value) for value in values)
		if processed <= TOLERANCE:
			frappe.throw(_("本次报工数量必须大于零"))
		if processed - available > TOLERANCE:
			frappe.throw(_("本次合格、损耗、次品和返修数量合计不能超过可报工数量 {0} {1}").format(
				available, self.uom or ""
			))
		if (flt(self.loss_qty) or flt(self.defective_qty) or flt(self.rework_qty)) and not (self.remarks or "").strip():
			frappe.throw(_("存在损耗、次品或返修数量时，请填写异常与备注"))
		self.pending_qty = max(available - processed, 0)
		_validate_downstream_quantity(self)


def _employee_can_operate(employee, operation):
	parents = frappe.get_all("Employee Operation Permission", filters={
		"employee": employee, "disabled": 0,
	}, pluck="name")
	return bool(parents and frappe.db.exists("Employee Operation Permission Operation", {
		"parent": ["in", parents], "operation": operation,
	}))


def _submitted_totals(flow_card, operation_row, exclude=None):
	conditions = {"production_flow_card": flow_card, "operation_row": operation_row, "docstatus": 1}
	if exclude:
		conditions["name"] = ["!=", exclude]
	rows = frappe.get_all(
		"Production Operation Report", filters=conditions,
		fields=["completed_qty", "loss_qty", "defective_qty", "rework_qty"],
	)
	return frappe._dict(
		completed=sum(flt(row.completed_qty) for row in rows),
		processed=sum(flt(row.completed_qty) + flt(row.loss_qty) + flt(row.defective_qty) + flt(row.rework_qty) for row in rows),
	)


def _operation_base_quantity(card, operation_row):
	rows = sorted(card.operations, key=lambda row: row.sequence_no or row.idx)
	index = next((idx for idx, row in enumerate(rows) if row.name == operation_row), None)
	if index is None:
		return 0
	if index == 0:
		return flt(card.production_qty)
	previous = rows[index - 1]
	previous_totals = _submitted_totals(card.name, previous.name)
	return previous_totals.completed if previous_totals.completed > TOLERANCE else flt(card.production_qty)


def _available_quantity(flow_card, operation_row, exclude=None):
	card = frappe.get_doc("Production Flow Card", flow_card)
	base = _operation_base_quantity(card, operation_row)
	used = _submitted_totals(flow_card, operation_row, exclude).processed
	return max(base - used, 0)


def _validate_downstream_quantity(report):
	card = frappe.get_doc("Production Flow Card", report.production_flow_card)
	current = next(row for row in card.operations if row.name == report.operation_row)
	projected_good = _submitted_totals(card.name, current.name, report.name).completed + flt(report.completed_qty)
	downstream_good = []
	for row in card.operations:
		if row.idx > current.idx:
			downstream_good.append(_submitted_totals(card.name, row.name).completed)
	if downstream_good and max(downstream_good) - projected_good > TOLERANCE:
		frappe.throw(_("前道补录的合格数量不能小于后道已经完成的数量 {0} {1}").format(
			max(downstream_good), report.uom or ""
		))


def _refresh_operation(flow_card, operation_row):
	card = frappe.get_doc("Production Flow Card", flow_card)
	row = next((item for item in card.operations if item.name == operation_row), None)
	if not row:
		return
	totals = _submitted_totals(flow_card, operation_row)
	base = _operation_base_quantity(card, operation_row)
	pending = max(base - totals.processed, 0)
	values = {"completed_qty": totals.completed, "pending_qty": pending}
	if totals.processed <= TOLERANCE:
		values.update(operation_status="待生产", actual_start=None, actual_end=None)
	elif pending <= TOLERANCE:
		values.update(operation_status="已完成", actual_end=now_datetime())
	else:
		values.update(operation_status="生产中", actual_end=None)
	if totals.processed > TOLERANCE and not row.actual_start:
		values["actual_start"] = now_datetime()
	frappe.db.set_value("Production Flow Card Operation", operation_row, values, update_modified=False)


def _scan_code(value, prefix):
	value = (value or "").strip()
	if not value:
		return ""
	value = re.sub(r"^https?://[^/]+/", "", value).rstrip("/").split("/")[-1]
	if "|" in value:
		parts = value.split("|")
		if parts[0].upper() == prefix:
			value = parts[1]
	return value.strip()


@frappe.whitelist()
def get_flow_card_context(flow_card_scan):
	code = _scan_code(flow_card_scan, "PFC")
	name = frappe.db.get_value("Production Flow Card", {"flow_card_no": code}, "name") or (
		code if frappe.db.exists("Production Flow Card", code) else None
	)
	if not name:
		frappe.throw(_("找不到生产流转卡：{0}").format(code))
	card = frappe.get_doc("Production Flow Card", name)
	card.check_permission("read")
	ensure_flow_card_open(card)
	operations = [_operation_data(card, row) for row in card.operations if row.operation_status != "已完成"]
	if not operations:
		frappe.throw(_("生产流转卡 {0} 的工序已经全部完成").format(card.flow_card_no or card.name))
	return {
		"production_flow_card": card.name,
		"flow_card_no": card.flow_card_no or card.name,
		"customer_name": frappe.db.get_value("Customer", card.customer, "customer_name") or card.customer,
		"finished_product_name": card.finished_product_name,
		"finished_specification": card.finished_specification,
		"color_no": card.color_no,
		"color": card.color,
		"production_qty": card.production_qty,
		"uom": card.finished_uom or "Kg",
		"delivery_date": card.delivery_date,
		"production_priority": card.production_priority or "普通",
		"current_progress_status": card.current_progress_status or card.production_status,
		"grey_fabric_batches": "、".join(row.batch_no for row in card.grey_fabric_issues if row.batch_no),
		"operation_total": len(card.operations),
		"operations": operations,
	}


@frappe.whitelist()
def resolve_employee_operation(flow_card, employee_scan):
	employee_code = _scan_code(employee_scan, "EMP")
	employee = frappe.db.get_value("Employee", {"attendance_device_id": employee_code}, "name") or (
		employee_code if frappe.db.exists("Employee", employee_code) else None
	)
	if not employee:
		frappe.throw(_("找不到员工：{0}").format(employee_code))
	details = frappe.db.get_value("Employee", employee, ["employee_name", "status"], as_dict=True)
	if details.status != "Active":
		frappe.throw(_("员工 {0} 不是在职状态").format(details.employee_name or employee))
	card = frappe.get_doc("Production Flow Card", flow_card)
	card.check_permission("read")
	permission_docs = frappe.get_all(
		"Employee Operation Permission", filters={"employee": employee, "disabled": 0}, pluck="name"
	)
	permissions = set(frappe.get_all(
		"Employee Operation Permission Operation",
		filters={"parent": ["in", permission_docs]} if permission_docs else {"parent": ""},
		pluck="operation",
	))
	candidates = [
		_operation_data(card, row) for row in card.operations
		if row.operation_status != "已完成" and row.operation in permissions
	]
	if not candidates:
		frappe.throw(_("员工 {0} 没有当前未完成工序的操作权限").format(details.employee_name or employee))
	active = [row for row in candidates if row["operation_status"] in ("生产中", "暂停")]
	selected = active[0] if len(active) == 1 else candidates[0] if len(candidates) == 1 else None
	return {
		"employee": employee,
		"employee_name": details.employee_name,
		"candidates": candidates,
		"selected": selected,
	}


def _operation_data(card, row):
	missing = [
		item.operation_name or item.operation for item in card.operations
		if item.idx < row.idx and item.operation_status != "已完成"
	]
	return {
		"operation_row": row.name,
		"operation": row.operation,
		"operation_name": row.operation_name or frappe.db.get_value("Production Operation", row.operation, "production_operation_name") or row.operation,
		"sequence_no": row.idx,
		"operation_status": row.operation_status,
		"production_resource": row.production_resource,
		"resource_name": row.resource_name or (frappe.db.get_value("Production Resource", row.production_resource, "resource_name") if row.production_resource else ""),
		"available_qty": _available_quantity(card.name, row.name),
		"missing_previous_operations": missing,
	}


@frappe.whitelist()
def validate_assistant(employee_scan):
	employee_code = _scan_code(employee_scan, "EMP")
	employee = frappe.db.get_value("Employee", {"attendance_device_id": employee_code}, "name") or (
		employee_code if frappe.db.exists("Employee", employee_code) else None
	)
	if not employee:
		frappe.throw(_("找不到员工：{0}").format(employee_code))
	details = frappe.db.get_value("Employee", employee, ["employee_name", "status"], as_dict=True)
	if details.status != "Active":
		frappe.throw(_("员工 {0} 不是在职状态").format(details.employee_name or employee))
	return {"employee": employee, "employee_name": details.employee_name}


@frappe.whitelist()
def submit_workbench_report(flow_card, operation_row, employees, completed_qty, production_resource=None,
	loss_qty=0, defective_qty=0, rework_qty=0, remarks=None):
	employees = frappe.parse_json(employees) or []
	if not employees:
		frappe.throw(_("请扫描员工"))
	doc = frappe.get_doc({
		"doctype": "Production Operation Report",
		"report_time": now_datetime(),
		"production_flow_card": flow_card,
		"operation_row": operation_row,
		"production_resource": production_resource,
		"completed_qty": flt(completed_qty),
		"loss_qty": flt(loss_qty),
		"defective_qty": flt(defective_qty),
		"rework_qty": flt(rework_qty),
		"remarks": remarks,
	})
	for index, employee in enumerate(employees):
		doc.append("employees", {
			"employee": employee.get("employee"),
			"employee_name": employee.get("employee_name"),
			"worker_role": "主操作员" if index == 0 else "协作人员",
			"scanned_at": now_datetime(),
		})
	doc.insert()
	doc.submit()
	return {"name": doc.name, "status": doc.report_status, "pending_qty": doc.pending_qty}

