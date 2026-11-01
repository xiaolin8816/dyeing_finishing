import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import getseries
from frappe.utils import cint, flt, getdate, now, nowdate
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry

from dyeing_finishing.dyeing_finishing.doctype.grey_fabric_customer_transfer.grey_fabric_customer_transfer import (
	_available_rows,
)
from dyeing_finishing.dyeing_finishing.doctype.grey_fabric_inventory_count.grey_fabric_inventory_count import (
	_scope_warehouse_names,
)


REVIEW_ROLES = {"Stock Manager", "System Manager"}
TOLERANCE = 0.000001


class GreyFabricLoss(Document):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._reset_amended_links()

	def insert(self, *args, **kwargs):
		self._reset_amended_links()
		return super().insert(*args, **kwargs)

	def _reset_amended_links(self):
		if self.get("amended_from") and cint(self.docstatus) == 0:
			self.status = "草稿"
			self.stock_entry = None
			self.reviewed_by = None
			self.reviewed_at = None
			self.review_remark = None

	def autoname(self):
		date = getdate(self.loss_date or nowdate())
		prefix = f"BS{date:%y%m%d}"
		self.name = f"{prefix}{getseries(prefix, 3)}"

	def before_insert(self):
		self.loss_no = self.name
		self.loss_date = self.loss_date or getdate(nowdate())
		self.status = "草稿"
		self.applicant = frappe.session.user
		self.stock_entry = None

	def validate(self):
		self.loss_no = self.name
		self.loss_date = self.loss_date or getdate(nowdate())
		self.customer_name = frappe.db.get_value("Customer", self.customer, "customer_name") or self.customer
		self._validate_items(refresh_snapshot=True)
		self._set_totals()

	def before_submit(self):
		self._validate_items(refresh_snapshot=True)
		self._set_totals()

	def on_submit(self):
		self.db_set("status", "待审核", update_modified=False)
		self.add_comment("Info", _("胚布报损单已提交，等待库存经理审核。"))

	def before_cancel(self):
		if not self.stock_entry:
			return
		stock_entry = self.stock_entry
		entry = frappe.get_doc("Stock Entry", stock_entry)
		self.db_set("stock_entry", None, update_modified=False)
		if entry.docstatus == 1:
			entry.update_stock_ledger = StockEntry.update_stock_ledger.__get__(entry, entry.__class__)
			entry.flags.from_grey_fabric_loss = True
			entry.cancel()
		self.db_set("stock_entry", stock_entry, update_modified=False)
		self.ignore_linked_doctypes = ("Stock Entry",)

	def on_cancel(self):
		self.db_set("status", "已取消", update_modified=False)

	def _validate_items(self, refresh_snapshot=False):
		if not self.customer:
			frappe.throw(_("请选择客户。"))
		if not (self.reason_details or "").strip():
			frappe.throw(_("请填写报损原因说明。"))
		if not self.items:
			frappe.throw(_("请至少选择一个报损批次。"))

		seen = set()
		warehouse_scope = set(_scope_warehouse_names(self.warehouse))
		if not warehouse_scope:
			frappe.throw(_("所选仓库不属于可用的胚布库存范围。"))
		company = None
		for row in self.items:
			key = (row.batch_no, row.source_warehouse)
			if not row.batch_no or key in seen:
				frappe.throw(_("报损明细存在重复批次。"))
			seen.add(key)
			source = _find_available(row.batch_no, self.customer, row.source_warehouse or self.warehouse)
			if not source:
				frappe.throw(_("批次 {0} 已无可报损库存、不属于当前客户或不在所选仓库。" ).format(row.batch_no))
			if source.source_warehouse not in warehouse_scope:
				frappe.throw(_("批次 {0} 不在所选仓库范围内。" ).format(row.batch_no))
			row_company = frappe.db.get_value("Warehouse", source.source_warehouse, "company")
			if company and company != row_company:
				frappe.throw(_("同一张胚布报损单不能跨公司。"))
			company = row_company

			for field in (
				"item_code", "item_name", "color", "source_warehouse", "location",
				"stock_roll_count", "stock_qty", "stock_uom", "source_receipt",
			):
				if refresh_snapshot or not row.get(field):
					row.set(field, source.get(field))

			row.loss_method = row.loss_method or "整匹报损"
			row.loss_qty = flt(row.loss_qty)
			row.loss_roll_count = flt(row.loss_roll_count)
			stock_qty = flt(source.stock_qty)
			stock_roll_count = flt(source.stock_roll_count)
			if row.loss_qty <= TOLERANCE:
				frappe.throw(_("批次 {0} 的报损重量必须大于 0。" ).format(row.batch_no))
			if row.loss_qty > stock_qty + TOLERANCE:
				frappe.throw(_("批次 {0} 的报损重量不能超过当前库存重量 {1} {2}。" ).format(
					row.batch_no, source.stock_qty, source.stock_uom or "",
				))
			if row.loss_method == "整匹报损":
				if row.loss_roll_count <= TOLERANCE:
					frappe.throw(_("批次 {0} 的报损匹数必须大于 0。" ).format(row.batch_no))
				if abs(row.loss_roll_count - cint(row.loss_roll_count)) > TOLERANCE:
					frappe.throw(_("批次 {0} 的报损匹数必须为整数。" ).format(row.batch_no))
				if row.loss_roll_count > stock_roll_count + TOLERANCE:
					frappe.throw(_("批次 {0} 的报损匹数不能超过当前库存匹数 {1}。" ).format(
						row.batch_no, stock_roll_count,
					))
				all_rolls = abs(row.loss_roll_count - stock_roll_count) <= TOLERANCE
				all_weight = abs(row.loss_qty - stock_qty) <= TOLERANCE
				if all_rolls != all_weight:
					frappe.throw(_(
						"批次 {0} 报损全部匹数时必须同时报损全部重量；只报损部分匹数时，报损重量必须小于全部库存重量。"
					).format(row.batch_no))
			elif row.loss_method == "部分重量损耗":
				if row.loss_qty >= stock_qty - TOLERANCE:
					frappe.throw(_("批次 {0} 的部分重量损耗必须小于当前库存重量；全部损失请使用整匹报损。" ).format(row.batch_no))
				row.loss_roll_count = 0
			else:
				frappe.throw(_("批次 {0} 的报损方式无效。" ).format(row.batch_no))

			row.remaining_roll_count = stock_roll_count - flt(row.loss_roll_count)
			row.remaining_qty = stock_qty - flt(row.loss_qty)

		self.company = company

	def _set_totals(self):
		self.total_batch_count = len(self.items or [])
		self.total_loss_roll_count = sum(flt(row.loss_roll_count) for row in self.items or [])
		self.total_loss_weight = sum(flt(row.loss_qty) for row in self.items or [])
		self.batch_summary = _summarize(self.items, "batch_no")
		self.item_name_summary = _summarize(self.items, "item_name")

	def _assert_stock_is_current(self):
		changed = []
		for row in self.items:
			source = _find_available(row.batch_no, self.customer, row.source_warehouse)
			current_rolls = flt(source.stock_roll_count) if source else 0
			current_qty = flt(source.stock_qty) if source else 0
			if abs(current_rolls - flt(row.stock_roll_count)) > TOLERANCE or abs(current_qty - flt(row.stock_qty)) > TOLERANCE:
				changed.append(_("{0}（当前 {1} 匹 / {2} {3}）").format(
					row.batch_no, current_rolls, current_qty, row.stock_uom or "",
				))
		if changed:
			frappe.throw(_("报损审核前库存已经变化，请驳回并重新建立报损单：<br>{0}").format("<br>".join(changed)))

	def _create_stock_entry(self):
		if self.stock_entry:
			return frappe.get_doc("Stock Entry", self.stock_entry)
		entry = frappe.get_doc({
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Issue",
			"purpose": "Material Issue",
			"company": self.company,
			"posting_date": self.loss_date,
			"custom_grey_fabric_loss": self.name,
			"remarks": _("胚布报损单：{0}；客户：{1}；原因：{2}；说明：{3}").format(
				self.name, self.customer_name, self.loss_type, self.reason_details,
			),
			"items": [{
				"item_code": row.item_code,
				"qty": flt(row.loss_qty),
				"uom": row.stock_uom,
				"s_warehouse": row.source_warehouse,
				"batch_no": row.batch_no,
				"use_serial_batch_fields": 1,
				"custom_roll_count": flt(row.loss_roll_count),
				"custom_grey_fabric_loss": self.name,
			} for row in self.items],
		})
		entry.insert(ignore_permissions=True)
		entry.submit()
		entry.add_comment("Info", _("由胚布报损单 {0} 审核生成。" ).format(self.name))
		return entry


def _summarize(rows, fieldname, limit=3):
	values = []
	for row in rows or []:
		value = str(row.get(fieldname) or "").strip()
		if value and value not in values:
			values.append(value)
	if len(values) <= limit:
		return "、".join(values)
	return _("{0}等{1}项").format("、".join(values[:limit]), len(values))


def _assert_can_review():
	if not REVIEW_ROLES.intersection(frappe.get_roles()):
		frappe.throw(_("只有库存经理或系统经理可以审核胚布报损单。"), frappe.PermissionError)


def _lock_loss(name):
	if not frappe.db.sql("SELECT name FROM `tabGrey Fabric Loss` WHERE name=%s FOR UPDATE", name):
		frappe.throw(_("胚布报损单 {0} 不存在。" ).format(name))
	return frappe.get_doc("Grey Fabric Loss", name)


@frappe.whitelist()
def approve_loss(name, review_remark=None):
	_assert_can_review()
	doc = _lock_loss(name)
	if doc.docstatus != 1 or doc.status != "待审核":
		frappe.throw(_("只有待审核的已提交胚布报损单可以审核通过。"))
	doc._assert_stock_is_current()
	entry = doc._create_stock_entry()
	doc.db_set({
		"status": "已审核",
		"reviewed_by": frappe.session.user,
		"reviewed_at": now(),
		"review_remark": (review_remark or "").strip() or None,
		"stock_entry": entry.name,
	})
	doc.add_comment("Info", _("胚布报损已由 {0} 审核通过，库存凭证：{1}。" ).format(
		frappe.session.user, entry.name,
	))
	return {"status": "已审核", "stock_entry": entry.name}


@frappe.whitelist()
def reject_loss(name, review_remark):
	_assert_can_review()
	if not (review_remark or "").strip():
		frappe.throw(_("驳回胚布报损单时必须填写审核意见。"))
	doc = _lock_loss(name)
	if doc.docstatus != 1 or doc.status != "待审核":
		frappe.throw(_("只有待审核的已提交胚布报损单可以驳回。"))
	doc.db_set({
		"status": "已驳回",
		"reviewed_by": frappe.session.user,
		"reviewed_at": now(),
		"review_remark": review_remark.strip(),
	})
	doc.add_comment("Info", _("胚布报损已由 {0} 驳回：{1}" ).format(frappe.session.user, review_remark.strip()))
	return {"status": "已驳回"}


def _find_available(batch_no, customer, warehouse=None):
	warehouse_scope = set(_scope_warehouse_names(warehouse)) if warehouse else set()
	return next((
		row for row in _available_rows(customer)
		if row.batch_no == batch_no and (not warehouse or row.source_warehouse in warehouse_scope)
	), None)


@frappe.whitelist()
def get_available_batches(doctype, txt, searchfield, start, page_len, filters, as_dict=False, **kwargs):
	filters = frappe.parse_json(filters) or {}
	excluded = set(frappe.parse_json(filters.get("excluded_names") or "[]") or [])
	warehouse = filters.get("warehouse")
	warehouse_scope = set(_scope_warehouse_names(warehouse)) if warehouse else set()
	rows = [
		row for row in _available_rows(filters.get("customer"))
		if row.batch_no not in excluded and (not warehouse or row.source_warehouse in warehouse_scope)
	]
	txt = (txt or "").lower()
	rows = [row for row in rows if not txt or txt in row.batch_no.lower() or txt in (row.item_name or "").lower()]
	rows = rows[cint(start):cint(start) + cint(page_len)]
	if as_dict:
		return [{
			"name": row.batch_no,
			"批次": row.batch_no,
			"胚布名称": row.item_name,
			"库存匹数": row.stock_roll_count,
			"库存重量": row.stock_qty,
			"仓库": row.source_warehouse,
		} for row in rows]
	return [[row.batch_no, row.item_name, row.stock_roll_count, row.stock_qty, row.source_warehouse] for row in rows]


@frappe.whitelist()
def get_batch_details(names, customer, warehouse=None):
	names = set(frappe.parse_json(names) or [])
	warehouse_scope = set(_scope_warehouse_names(warehouse)) if warehouse else set()
	return [
		row for row in _available_rows(customer)
		if row.batch_no in names and (not warehouse or row.source_warehouse in warehouse_scope)
	]


def handle_stock_entry_cancel(doc, method=None):
	if not doc.get("custom_grey_fabric_loss") or doc.flags.from_grey_fabric_loss:
		return
	if frappe.form_dict.get("cmd") == "frappe.desk.form.linked_with.cancel_all_linked_docs":
		doc.update_stock_ledger = StockEntry.update_stock_ledger.__get__(doc, doc.__class__)
		doc.flags.from_grey_fabric_loss = True
		doc.flags.ignore_links = True
		return
	loss = frappe.get_doc("Grey Fabric Loss", doc.custom_grey_fabric_loss)
	if loss.docstatus == 1:
		frappe.throw(_("请通过胚布报损单 {0} 执行取消。" ).format(loss.name))
