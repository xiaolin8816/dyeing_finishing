import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import getseries
from frappe.utils import cint, flt, getdate, now, nowdate
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry

from dyeing_finishing.dyeing_finishing.doctype.grey_fabric_customer_transfer.grey_fabric_customer_transfer import _available_rows


class CustomerGreyFabricReturn(Document):
	def insert(self, *args, **kwargs):
		self._reset_amended_links()
		return super().insert(*args, **kwargs)

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._reset_amended_links()

	def _reset_amended_links(self):
		if self.get("amended_from") and cint(self.docstatus) == 0:
			self.stock_entry = None
			self.confirmed_at = None

	def autoname(self):
		date = getdate(self.return_date or nowdate())
		prefix = f"PT{date:%y%m%d}"
		self.name = f"{prefix}{getseries(prefix, 3)}"

	def before_insert(self):
		self.return_no = self.name
		self.return_status = "保存"
		self.operator = frappe.session.user
		self.stock_entry = None
		self.confirmed_at = None

	def validate(self):
		self.return_no = self.name
		self.return_date = self.return_date or getdate(nowdate())
		self.customer_name = frappe.db.get_value("Customer", self.customer, "customer_name") or self.customer
		self._validate_items()
		self._set_totals()

	def on_submit(self):
		self._create_stock_entry()
		self.db_set({"return_status": "已退货", "operator": frappe.session.user, "confirmed_at": now()}, update_modified=False)

	def before_cancel(self):
		if not self.stock_entry:
			return
		stock_entry = self.stock_entry
		entry = frappe.get_doc("Stock Entry", stock_entry)
		self.db_set("stock_entry", None, update_modified=False)
		if entry.docstatus == 1:
			entry.update_stock_ledger = StockEntry.update_stock_ledger.__get__(entry, entry.__class__)
			entry.flags.from_customer_grey_fabric_return = True
			entry.cancel()
		self.db_set("stock_entry", stock_entry, update_modified=False)
		self.ignore_linked_doctypes = ("Stock Entry",)

	def on_cancel(self):
		self.db_set("return_status", "已取消", update_modified=False)

	def _validate_items(self):
		if not self.customer:
			frappe.throw(_("请先选择客户。"))
		if not self.items:
			frappe.throw(_("请至少选择一个可退胚布批次。"))
		seen = set()
		warehouse = None
		for row in self.items:
			key = (row.batch_no, row.source_warehouse)
			if not row.batch_no or key in seen:
				frappe.throw(_("胚布退货明细存在重复批次。"))
			seen.add(key)
			source = _find_available(row.batch_no, self.customer, row.source_warehouse)
			if not source:
				frappe.throw(_("批次 {0} 已无可退库存、已进入生产，或不属于当前客户。").format(row.batch_no))
			if warehouse and warehouse != source.source_warehouse:
				frappe.throw(_("同一张胚布退货单只能选择同一仓库或货位的库存。"))
			warehouse = source.source_warehouse
			for field in ("item_code", "item_name", "color", "source_warehouse", "location", "stock_roll_count", "stock_qty", "stock_uom", "source_receipt"):
				row.set(field, source.get(field))
			if cint(row.return_roll_count) <= 0 or flt(row.return_roll_count) > flt(source.stock_roll_count) + 0.000001:
				frappe.throw(_("批次 {0} 的退货匹数必须大于0且不能超过库存匹数。").format(row.batch_no))
			if flt(row.return_qty) <= 0 or flt(row.return_qty) > flt(source.stock_qty) + 0.000001:
				frappe.throw(_("批次 {0} 的退货数量必须大于0且不能超过库存数量。").format(row.batch_no))
			row.remaining_roll_count = flt(source.stock_roll_count) - cint(row.return_roll_count)
			row.remaining_qty = flt(source.stock_qty) - flt(row.return_qty)
		self.source_warehouse = warehouse

	def _set_totals(self):
		self.total_batch_count = len(self.items or [])
		self.total_roll_count = sum(cint(row.return_roll_count) for row in self.items or [])
		self.total_weight = sum(flt(row.return_qty) for row in self.items or [])

	def _create_stock_entry(self):
		if self.stock_entry:
			return
		company = frappe.db.get_value("Warehouse", self.source_warehouse, "company")
		if not company:
			frappe.throw(_("退货仓库未设置公司。"))
		entry = frappe.get_doc({
			"doctype": "Stock Entry", "stock_entry_type": "Material Issue", "purpose": "Material Issue",
			"company": company, "posting_date": self.return_date,
			"custom_customer_grey_fabric_return": self.name,
			"remarks": _("客户胚布退货单：{0}；客户：{1}").format(self.name, self.customer_name),
			"items": [{
				"item_code": row.item_code, "qty": flt(row.return_qty), "uom": row.stock_uom,
				"s_warehouse": row.source_warehouse, "batch_no": row.batch_no,
				"use_serial_batch_fields": 1, "custom_roll_count": cint(row.return_roll_count),
				"custom_customer_grey_fabric_return": self.name,
			} for row in self.items],
		})
		entry.insert(ignore_permissions=True)
		entry.submit()
		self.db_set("stock_entry", entry.name, update_modified=False)


def _return_rows(customer=None):
	rows = [
		row for row in _available_rows(customer)
		if row.source_warehouse == "胚布仓库 - 沅泰" or row.location == "胚布货位 - 沅泰"
	]
	batch_names = [row.batch_no for row in rows]
	receipts = {}
	if batch_names:
		for row in frappe.db.sql("""SELECT item.batch_no, MAX(receipt.name) source_receipt
			FROM `tabCustomer Grey Fabric Receipt Item` item
			INNER JOIN `tabCustomer Grey Fabric Receipt` receipt ON receipt.name=item.parent AND receipt.docstatus=1
			WHERE item.batch_no IN %(batches)s GROUP BY item.batch_no""", {"batches": batch_names}, as_dict=True):
			receipts[row.batch_no] = row.source_receipt
	for row in rows:
		if row.location == "胚布货位 - 沅泰":
			row.location = row.source_warehouse
		row.stock_uom = frappe.db.get_value("Item", row.item_code, "stock_uom")
		row.source_receipt = receipts.get(row.batch_no)
	return rows


def _find_available(batch_no, customer, warehouse=None):
	return next((row for row in _return_rows(customer) if row.batch_no == batch_no and (not warehouse or row.source_warehouse == warehouse)), None)


@frappe.whitelist()
def get_available_batches(doctype, txt, searchfield, start, page_len, filters, as_dict=False, **kwargs):
	filters = frappe.parse_json(filters) or {}
	excluded = set(frappe.parse_json(filters.get("excluded_names") or "[]") or [])
	txt = (txt or "").lower()
	rows = [row for row in _return_rows(filters.get("customer")) if row.batch_no not in excluded]
	rows = [row for row in rows if not txt or txt in row.batch_no.lower() or txt in (row.item_name or "").lower()]
	rows = rows[cint(start):cint(start) + cint(page_len)]
	if as_dict:
		return [{"name": row.batch_no, "胚布名称": row.item_name, "库存匹数": row.stock_roll_count, "库存数量": row.stock_qty, "仓库/货位": row.source_warehouse} for row in rows]
	return [[row.batch_no, row.item_name, row.stock_roll_count, row.stock_qty, row.source_warehouse] for row in rows]


@frappe.whitelist()
def get_batch_details(names, customer):
	names = set(frappe.parse_json(names) or [])
	return [row for row in _return_rows(customer) if row.batch_no in names]


def handle_stock_entry_cancel(doc, method=None):
	if not doc.get("custom_customer_grey_fabric_return") or doc.flags.from_customer_grey_fabric_return:
		return
	if frappe.form_dict.get("cmd") == "frappe.desk.form.linked_with.cancel_all_linked_docs":
		doc.update_stock_ledger = StockEntry.update_stock_ledger.__get__(doc, doc.__class__)
		doc.flags.from_customer_grey_fabric_return = True
		doc.flags.ignore_links = True
		return
	return_doc = frappe.get_doc("Customer Grey Fabric Return", doc.custom_customer_grey_fabric_return)
	if return_doc.docstatus == 1:
		frappe.throw(_("请通过客户胚布退货单 {0} 执行取消。").format(return_doc.name))
