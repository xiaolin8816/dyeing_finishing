import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import getseries
from frappe.utils import cint, flt, getdate, nowdate
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry

from dyeing_finishing.dyeing_finishing.doctype.production_flow_card.production_flow_card import (
	ensure_flow_card_open,
	record_production_progress,
	remove_production_progress,
)
from dyeing_finishing.dyeing_finishing.settings import get_setting


class FinishedProductDelivery(Document):
	def autoname(self):
		date = getdate(self.delivery_date or nowdate())
		prefix = f"CK{date:%y%m%d}"
		self.name = f"{prefix}{getseries(prefix, 3)}"

	def before_insert(self):
		self.delivery_no = self.name
		self.delivery_date = self.delivery_date or getdate(nowdate())
		self.delivery_status = "保存"

	def validate(self):
		self.delivery_no = self.name
		self.delivery_date = self.delivery_date or getdate(nowdate())
		self.source_warehouse = get_setting("finished_product_warehouse")
		self._set_flow_card_details()
		self._validate_and_refresh_items()
		self._set_totals()
		self._set_available_summary()

	def before_submit(self):
		self._validate_and_refresh_items()
		self._set_totals()
		if not cint(get_setting("allow_partial_delivery")):
			available_names = {row.name for row in get_available_rolls(self.production_flow_card)}
			selected_names = {row.packing_receipt_item for row in self.items}
			if selected_names != available_names:
				frappe.throw(_("系统设置不允许分批成品出库，请选择当前全部可出库成品卷。"))

	def on_submit(self):
		self._create_stock_entry()
		self.db_set("delivery_status", "已出库", update_modified=False)
		for row in self.items:
			frappe.db.set_value(
				"Finished Product Packing Receipt Item", row.packing_receipt_item,
				"warehouse_status", "已出库", update_modified=False,
			)
		self._record_progress("成品已出库")
		refresh_delivery_progress(self.production_flow_card)

	def before_cancel(self):
		_ensure_no_submitted_returns(self.name)

	def on_cancel(self):
		stock_entry = self.stock_entry
		if stock_entry:
			self.db_set("stock_entry", None, update_modified=False)
			entry = frappe.get_doc("Stock Entry", stock_entry)
			if entry.docstatus == 1:
				entry.update_stock_ledger = StockEntry.update_stock_ledger.__get__(entry, entry.__class__)
				entry.flags.from_finished_product_delivery = True
				entry.cancel()
		for row in self.items:
			frappe.db.set_value(
				"Finished Product Packing Receipt Item", row.packing_receipt_item,
				"warehouse_status", "已入库", update_modified=False,
			)
		self.db_set("delivery_status", "已取消", update_modified=False)
		self._record_progress("成品出库已取消")
		refresh_delivery_progress(self.production_flow_card)

	def on_trash(self):
		remove_production_progress(self.doctype, self.name)

	def _set_flow_card_details(self):
		if not self.production_flow_card:
			frappe.throw(_("请选择生产流转卡"))
		card = frappe.get_doc("Production Flow Card", self.production_flow_card)
		ensure_flow_card_open(card)
		self.company = card.company or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
			"Global Defaults", "default_company"
		)
		packing = frappe.db.get_value(
			"Finished Product Packing Receipt",
			{"production_flow_card": card.name, "docstatus": 1, "packing_status": "已入库"},
			["sales_order", "customer", "customer_name", "finished_item_code", "finished_batch_no",
			 "finished_product_name", "finished_specification", "color_no", "color", "target_warehouse"],
			as_dict=True,
		)
		if not packing:
			frappe.throw(_("生产流转卡 {0} 尚无已入库成品").format(card.name))
		self.sales_order = packing.sales_order
		self.customer = packing.customer
		self.customer_name = packing.customer_name
		self.finished_item_code = packing.finished_item_code
		self.finished_batch_no = packing.finished_batch_no
		self.finished_product_name = packing.finished_product_name
		self.finished_specification = packing.finished_specification
		self.color_no = packing.color_no
		self.color = packing.color
		self.source_warehouse = packing.target_warehouse or get_setting("finished_product_warehouse")

	def _validate_and_refresh_items(self):
		if not self.items:
			frappe.throw(_("请至少选择一卷成品"))
		seen = set()
		allocation = None
		identity = None
		for row in self.items:
			if not row.packing_receipt_item or row.packing_receipt_item in seen:
				frappe.throw(_("成品出库明细存在重复卷"))
			seen.add(row.packing_receipt_item)
			source = _packing_item(row.packing_receipt_item)
			if not source or source.production_flow_card != self.production_flow_card:
				frappe.throw(_("成品卷 {0} 不属于当前生产流转卡").format(row.roll_no or row.packing_receipt_item))
			if source.warehouse_status != "已入库":
				frappe.throw(_("成品卷 {0} 当前状态为 {1}，不能出库").format(source.roll_no, source.warehouse_status))
			used_by = frappe.db.get_value(
				"Finished Product Delivery Item",
				{"packing_receipt_item": row.packing_receipt_item, "parent": ["!=", self.name], "docstatus": 1},
				"parent",
			)
			if used_by:
				frappe.throw(_("成品卷 {0} 已在出库单 {1} 出库").format(source.roll_no, used_by))
			current = (source.allocated_customer, source.allocated_sales_order, source.allocated_sales_order_item)
			if allocation and current != allocation:
				frappe.throw(_("同一张成品出库单只能选择当前客户和订单相同的成品卷。"))
			allocation = current
			current_identity = (source.allocated_finished_item_code, source.finished_batch_no)
			if identity and current_identity != identity:
				frappe.throw(_("同一张成品出库单只能选择当前成品物料和批次相同的成品卷。"))
			identity = current_identity
			for fieldname in (
				"roll_no", "source_packing_receipt", "piece_no", "finished_batch_no", "weight",
				"weight_uom", "yard_qty", "yard_uom", "finished_grade", "quality_flag",
				"grey_fabric_batch", "package_no", "allocated_customer", "allocated_customer_name",
				"allocated_sales_order", "allocated_sales_order_item", "customer_transfer",
				"allocated_finished_item_code", "allocated_finished_product_name", "allocated_finished_specification",
				"allocated_color_no", "allocated_color",
			):
				row.set(fieldname, source.get(fieldname))
		if allocation:
			self.customer, self.sales_order, _sales_order_item = allocation
			self.customer_name = frappe.db.get_value("Customer", self.customer, "customer_name") or self.customer
		if identity:
			first = self.items[0]
			self.finished_item_code = first.allocated_finished_item_code
			self.finished_batch_no = first.finished_batch_no
			self.finished_product_name = first.allocated_finished_product_name
			self.finished_specification = first.allocated_finished_specification
			self.color_no = first.allocated_color_no
			self.color = first.allocated_color

	def _set_totals(self):
		self.total_roll_count = len(self.items or [])
		self.total_weight = sum(flt(row.weight) for row in self.items or [])
		self.total_yard_qty = sum(flt(row.yard_qty) for row in self.items or [])

	def _set_available_summary(self):
		rows = get_available_rolls(self.production_flow_card)
		self.available_roll_count = len(rows)
		self.available_weight = sum(flt(row.weight) for row in rows)
		self.available_yard_qty = sum(flt(row.yard_qty) for row in rows)

	def _create_stock_entry(self):
		if self.stock_entry:
			return
		if not frappe.db.exists("Warehouse", self.source_warehouse):
			frappe.throw(_("未找到仓库：{0}").format(self.source_warehouse))
		company = frappe.db.get_value("Warehouse", self.source_warehouse, "company")
		entry = frappe.get_doc({
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Issue",
			"purpose": "Material Issue",
			"company": company,
			"posting_date": self.delivery_date,
			"from_warehouse": self.source_warehouse,
			"custom_finished_product_delivery": self.name,
			"remarks": _("\u6210\u54c1\u51fa\u5e93\u5355\uff1a{0}\uff1b\u751f\u4ea7\u6d41\u8f6c\u5361\uff1a{1}").format(self.name, self.production_flow_card),
			"items": [{
				"item_code": self.finished_item_code,
				"qty": flt(self.total_weight),
				"uom": get_setting("weight_uom"),
				"s_warehouse": self.source_warehouse,
				"batch_no": self.finished_batch_no,
				"use_serial_batch_fields": 1,
				"allow_zero_valuation_rate": 1,
				"custom_roll_count": self.total_roll_count,
				"custom_yard_qty": self.total_yard_qty,
				"custom_yard_uom": get_setting("yard_uom"),
				"custom_production_flow_card": self.production_flow_card,
				"custom_finished_product_delivery": self.name,
			}],
		})
		entry.insert(ignore_permissions=True)
		entry.submit()
		self.db_set("stock_entry", entry.name, update_modified=False)

	def _record_progress(self, status):
		description = _("\u51fa\u5e93 {0} \u5339\uff0c{1} Kg\uff0c{2} Y").format(
			self.total_roll_count, self.total_weight, self.total_yard_qty
		)
		filters = {"parent": self.production_flow_card, "source_doctype": self.doctype, "source_document": self.name}
		name = frappe.db.get_value("Production Flow Card Progress", filters, "name")
		if name:
			frappe.db.set_value("Production Flow Card Progress", name, {"progress_status": status, "description": description}, update_modified=False)
		else:
			record_production_progress(
				self.production_flow_card, "成品出库", status, self.doctype, self.name,
				batch_no=self.finished_batch_no, quantity=self.total_weight, uom=get_setting("weight_uom"),
				roll_count=self.total_roll_count, yard_qty=self.total_yard_qty, description=description,
			)


def _packing_item(name):
	rows = frappe.db.sql(
		"""SELECT item.name, item.roll_no, item.piece_no, item.weight, item.weight_uom,
			item.yard_qty, item.yard_uom, item.finished_grade, item.quality_flag,
			item.grey_fabric_batch, item.package_no, item.warehouse_status,
			parent.name AS source_packing_receipt, parent.production_flow_card,
			COALESCE(NULLIF(item.current_finished_batch_no, ''), parent.finished_batch_no) AS finished_batch_no,
			COALESCE(NULLIF(item.current_finished_item_code, ''), parent.finished_item_code) AS allocated_finished_item_code,
			COALESCE(NULLIF(item.current_finished_product_name, ''), parent.finished_product_name) AS allocated_finished_product_name,
			COALESCE(NULLIF(item.current_finished_specification, ''), parent.finished_specification) AS allocated_finished_specification,
			COALESCE(NULLIF(item.current_color_no, ''), parent.color_no) AS allocated_color_no,
			COALESCE(NULLIF(item.current_color, ''), parent.color) AS allocated_color,
			COALESCE(NULLIF(item.current_customer, ''), parent.customer) AS allocated_customer,
			COALESCE(NULLIF(item.current_customer_name, ''), parent.customer_name) AS allocated_customer_name,
			COALESCE(NULLIF(item.current_sales_order, ''), parent.sales_order) AS allocated_sales_order,
			COALESCE(NULLIF(item.current_sales_order_item, ''), parent.sales_order_item) AS allocated_sales_order_item,
			item.customer_transfer
		FROM `tabFinished Product Packing Receipt Item` item
		INNER JOIN `tabFinished Product Packing Receipt` parent ON parent.name = item.parent
		WHERE item.name = %s AND parent.docstatus = 1 AND parent.packing_status = '已入库'""",
		name, as_dict=True,
	)
	return rows[0] if rows else None


def get_available_rolls(flow_card):
	if not flow_card:
		return []
	return frappe.db.sql(
		"""SELECT item.name, item.roll_no, item.piece_no, item.weight, item.weight_uom,
			item.yard_qty, item.yard_uom, item.finished_grade, item.quality_flag,
			item.grey_fabric_batch, item.package_no, parent.name AS source_packing_receipt,
			COALESCE(NULLIF(item.current_finished_batch_no, ''), parent.finished_batch_no) AS finished_batch_no,
			COALESCE(NULLIF(item.current_finished_item_code, ''), parent.finished_item_code) AS allocated_finished_item_code,
			COALESCE(NULLIF(item.current_finished_product_name, ''), parent.finished_product_name) AS allocated_finished_product_name,
			COALESCE(NULLIF(item.current_finished_specification, ''), parent.finished_specification) AS allocated_finished_specification,
			COALESCE(NULLIF(item.current_color_no, ''), parent.color_no) AS allocated_color_no,
			COALESCE(NULLIF(item.current_color, ''), parent.color) AS allocated_color,
			COALESCE(NULLIF(item.current_customer, ''), parent.customer) AS allocated_customer,
			COALESCE(NULLIF(item.current_customer_name, ''), parent.customer_name) AS allocated_customer_name,
			COALESCE(NULLIF(item.current_sales_order, ''), parent.sales_order) AS allocated_sales_order,
			COALESCE(NULLIF(item.current_sales_order_item, ''), parent.sales_order_item) AS allocated_sales_order_item,
			item.customer_transfer
		FROM `tabFinished Product Packing Receipt Item` item
		INNER JOIN `tabFinished Product Packing Receipt` parent ON parent.name = item.parent
		WHERE parent.production_flow_card = %(flow_card)s
			AND parent.docstatus = 1 AND parent.packing_status = '已入库'
			AND item.warehouse_status = '已入库'
			AND NOT EXISTS (
				SELECT 1 FROM `tabFinished Product Delivery Item` delivery_item
				WHERE delivery_item.packing_receipt_item = item.name AND delivery_item.docstatus = 1
			)
		ORDER BY parent.packing_date, parent.creation, item.idx""",
		{"flow_card": flow_card}, as_dict=True,
	)


@frappe.whitelist()
def get_delivery_flow_card_details(flow_card):
	card = frappe.get_doc("Production Flow Card", flow_card)
	ensure_flow_card_open(card)
	rows = get_available_rolls(flow_card)
	packing = frappe.db.get_value(
		"Finished Product Packing Receipt",
		{"production_flow_card": flow_card, "docstatus": 1, "packing_status": "已入库"},
		["sales_order", "customer", "customer_name", "finished_item_code", "finished_batch_no",
		 "finished_product_name", "finished_specification", "color_no", "color", "target_warehouse"],
		as_dict=True,
	)
	if not packing:
		frappe.throw(_("该流转卡尚无已入库成品"))
	return {**packing, "available_roll_count": len(rows),
		"available_weight": sum(flt(row.weight) for row in rows),
		"available_yard_qty": sum(flt(row.yard_qty) for row in rows)}


@frappe.whitelist()
def get_available_finished_rolls(doctype, txt, searchfield, start, page_len, filters, as_dict=False, **kwargs):
	filters = frappe.parse_json(filters) or {}
	rows = get_available_rolls(filters.get("production_flow_card"))
	excluded_names = set(frappe.parse_json(filters.get("excluded_names") or "[]") or [])
	rows = [row for row in rows if row.name not in excluded_names]
	txt = (txt or "").lower()
	rows = [row for row in rows if not txt or txt in row.roll_no.lower() or txt in row.source_packing_receipt.lower()]
	rows = rows[start:start + page_len]
	if as_dict:
		return [
			{
				"name": row.name,
				"匹号": row.piece_no,
				"重量 (Kg)": row.weight,
				"码数 (Y)": row.yard_qty,
				"当前客户": row.allocated_customer_name,
				"成品卷号": row.roll_no,
				"来源包装入库单": row.source_packing_receipt,
			}
			for row in rows
		]
	return [[row.name, row.piece_no, row.roll_no, row.source_packing_receipt, row.weight, row.yard_qty] for row in rows]


@frappe.whitelist()
def get_finished_roll_details(names):
	names = frappe.parse_json(names) or []
	return [row for name in names if (row := _packing_item(name))]


def refresh_delivery_progress(flow_card):
	rows = get_available_rolls(flow_card)
	submitted_count = frappe.db.count("Finished Product Delivery", {"production_flow_card": flow_card, "docstatus": 1})
	if submitted_count:
		production_status = frappe.db.get_value("Production Flow Card", flow_card, "production_status")
		status = "成品全部出库" if production_status == "已完成" and not rows else "成品部分出库"
		frappe.db.set_value("Production Flow Card", flow_card, "current_progress_status", status, update_modified=False)
	else:
		from dyeing_finishing.dyeing_finishing.doctype.finished_product_customer_transfer.finished_product_customer_transfer import (
			refresh_customer_transfer_progress,
		)
		refresh_customer_transfer_progress(flow_card)


def handle_stock_entry_cancel(doc, method=None):
	if not doc.get("custom_finished_product_delivery") or doc.flags.from_finished_product_delivery:
		return
	delivery = frappe.get_doc("Finished Product Delivery", doc.custom_finished_product_delivery)
	if delivery.docstatus != 1:
		return
	_ensure_no_submitted_returns(delivery.name)
	delivery.db_set({"stock_entry": None, "delivery_status": "保存"}, update_modified=False)
	for row in delivery.items:
		frappe.db.set_value("Finished Product Packing Receipt Item", row.packing_receipt_item, "warehouse_status", "已入库", update_modified=False)
	delivery._record_progress("成品出库凭证已取消")
	refresh_delivery_progress(delivery.production_flow_card)


def _ensure_no_submitted_returns(delivery):
	linked_return = frappe.db.sql(
		"""SELECT parent.name
		FROM `tabFinished Product Return` parent
		INNER JOIN `tabFinished Product Return Item` item ON item.parent=parent.name
		WHERE parent.docstatus=1 AND item.source_delivery=%s LIMIT 1""",
		delivery,
	)
	if linked_return:
		frappe.throw(_("成品出库单 {0} 已产生退货处理单 {1}，不能取消出库；请先取消对应退货单。")
			.format(delivery, linked_return[0][0]))
