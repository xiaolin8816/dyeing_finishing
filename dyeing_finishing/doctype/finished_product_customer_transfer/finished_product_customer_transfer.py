import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import getseries
from frappe.utils import cint, flt, getdate, now, nowdate
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry

from dyeing_finishing.dyeing_finishing.item import get_or_create_finished_item
from dyeing_finishing.dyeing_finishing.settings import get_setting
from dyeing_finishing.dyeing_finishing.doctype.production_flow_card.production_flow_card import (
	record_production_progress,
	remove_production_progress,
)


class FinishedProductCustomerTransfer(Document):
	def autoname(self):
		date = getdate(self.transfer_date or nowdate())
		prefix = f"ZK{date:%y%m%d}"
		self.name = f"{prefix}{getseries(prefix, 3)}"

	def before_insert(self):
		self.transfer_no = self.name
		self.transfer_date = self.transfer_date or getdate(nowdate())
		self.transfer_status = "保存"
		self.operator = frappe.session.user

	def validate(self):
		self.transfer_no = self.name
		self._set_flow_card_details()
		self._validate_and_refresh_items()
		self._set_target_details()
		self._set_totals()

	def on_submit(self):
		if self.quality_confirmation == "需回修":
			frappe.throw(_("需回修的成品不能直接转客户，请改用成品库存转胚布仓流程。"))
		self._validate_and_refresh_items()
		self._set_target_details()
		self._create_stock_entry()
		for row in self.items:
			frappe.db.set_value(
				"Finished Product Packing Receipt Item", row.packing_receipt_item,
				{
					"current_customer": self.target_customer,
					"current_customer_name": self.target_customer_name,
					"current_sales_order": self.target_sales_order,
					"current_sales_order_item": self.target_sales_order_item,
					"customer_transfer": self.name,
					"current_finished_item_code": self.finished_item_code,
					"current_finished_batch_no": self.finished_batch_no,
					"current_finished_product_name": self.finished_product_name,
					"current_finished_specification": self.finished_specification,
					"current_color_no": self.color_no,
					"current_color": self.color,
				}, update_modified=False,
			)
		self.db_set({"transfer_status": "已确认", "confirmed_by": frappe.session.user, "confirmed_at": now()}, update_modified=False)
		self._record_progress()
		refresh_customer_transfer_progress(self.production_flow_card)
		frappe.get_doc("Production Flow Card", self.production_flow_card).add_comment(
			"Info", _("\u6210\u54c1\u8f6c\u5ba2\u6237\u5355 {0}\uff1a{1} \u2192 {2}\uff0c\u5171 {3} \u5339\u3002").format(
				self.name, self.source_customer_name, self.target_customer_name, self.total_roll_count
			),
		)

	def before_cancel(self):
		for row in self.items:
			item = frappe.db.get_value(
				"Finished Product Packing Receipt Item", row.packing_receipt_item,
				["warehouse_status", "customer_transfer"], as_dict=True,
			)
			if not item or item.warehouse_status != "已入库":
				frappe.throw(_("成品卷 {0} 已发生出库或转仓，不能取消转客户。").format(row.roll_no))
			if item.customer_transfer != self.name:
				frappe.throw(_("成品卷 {0} 已有后续转客户记录，请先取消后续单据。").format(row.roll_no))
		if self.stock_entry:
			stock_entry = self.stock_entry
			entry = frappe.get_doc("Stock Entry", stock_entry)
			self.db_set("stock_entry", None, update_modified=False)
			if entry.docstatus == 1:
				entry.update_stock_ledger = StockEntry.update_stock_ledger.__get__(entry, entry.__class__)
				entry.flags.from_finished_product_customer_transfer = True
				entry.cancel()
			self.db_set("stock_entry", stock_entry, update_modified=False)

	def on_cancel(self):
		for row in self.items:
			source_product = _finished_item_details(row.source_finished_item_code)
			frappe.db.set_value(
				"Finished Product Packing Receipt Item", row.packing_receipt_item,
				{
					"current_customer": self.source_customer,
					"current_customer_name": self.source_customer_name,
					"current_sales_order": self.source_sales_order,
					"current_sales_order_item": self.source_sales_order_item,
					"customer_transfer": _previous_transfer(row.packing_receipt_item, self.name),
					"current_finished_item_code": row.source_finished_item_code,
					"current_finished_batch_no": row.finished_batch_no,
					"current_finished_product_name": source_product.item_name,
					"current_finished_specification": source_product.finished_specification,
					"current_color_no": source_product.color_no,
					"current_color": source_product.color,
				}, update_modified=False,
			)
		self.db_set("transfer_status", "已取消", update_modified=False)
		remove_production_progress(self.doctype, self.name)
		refresh_customer_transfer_progress(self.production_flow_card)

	def on_trash(self):
		remove_production_progress(self.doctype, self.name)

	def _set_flow_card_details(self):
		if not self.production_flow_card:
			frappe.throw(_("请选择生产流转卡"))
		packing = _packing_header(self.production_flow_card)
		if not packing:
			frappe.throw(_("生产流转卡 {0} 尚无已入库成品。").format(self.production_flow_card))
		self.source_warehouse = packing.target_warehouse or get_setting("finished_product_warehouse")
		if not self.items:
			self.source_sales_order = packing.sales_order
			self.source_customer = packing.customer
			self.source_customer_name = packing.customer_name

	def _set_target_details(self):
		if not self.target_sales_order:
			return
		order = frappe.db.get_value(
			"Dyeing Sales Order", self.target_sales_order,
			["customer", "customer_name", "docstatus"], as_dict=True,
		)
		if not order or order.docstatus != 1:
			frappe.throw(_("新染整销售订单必须已提交。"))
		self.target_customer = order.customer
		self.target_customer_name = order.customer_name or frappe.db.get_value("Customer", order.customer, "customer_name") or order.customer
		if self.target_customer == self.source_customer:
			frappe.throw(_("新客户与原客户相同，无需制作成品转客户单。"))
		if not self.target_sales_order_item:
			return
		item = frappe.db.get_value(
			"Dyeing Sales Order Item", self.target_sales_order_item,
			["parent", "finished_product_name", "finished_specification", "color_no", "color", "finished_width", "finished_gsm", "finished_gsm_uom"], as_dict=True,
		)
		if not item or item.parent != self.target_sales_order:
			frappe.throw(_("新销售订单明细不属于所选订单。"))
		if not item.finished_product_name or not item.color_no:
			frappe.throw(_("新销售订单明细必须填写成品名称和色号。"))
		self.finished_product_name = item.finished_product_name
		self.finished_specification = item.finished_specification
		self.color_no = item.color_no
		self.color = item.color
		self.finished_item_code = get_or_create_finished_item(
			item.color_no, item.finished_product_name, item.finished_width, item.finished_gsm, item.finished_gsm_uom
		)
		if self.finished_item_code == self.source_finished_item_code:
			self.finished_batch_no = self.source_finished_batch_no
		elif self.finished_batch_no and frappe.db.get_value("Batch", self.finished_batch_no, "item") != self.finished_item_code:
			self.finished_batch_no = None

	def _validate_and_refresh_items(self):
		if not self.items:
			frappe.throw(_("请至少选择一卷成品。"))
		seen = set()
		allocation = None
		identity = None
		for row in self.items:
			if not row.packing_receipt_item or row.packing_receipt_item in seen:
				frappe.throw(_("成品转客户明细存在重复卷。"))
			seen.add(row.packing_receipt_item)
			source = _packing_item(row.packing_receipt_item)
			if not source or source.production_flow_card != self.production_flow_card:
				frappe.throw(_("成品卷 {0} 不属于当前生产流转卡。").format(row.roll_no or row.packing_receipt_item))
			if source.warehouse_status != "已入库":
				frappe.throw(_("成品卷 {0} 当前状态为 {1}，不能转客户。").format(source.roll_no, source.warehouse_status))
			current = (source.allocated_customer, source.allocated_sales_order, source.allocated_sales_order_item)
			if allocation and current != allocation:
				frappe.throw(_("同一张转客户单只能选择当前客户和订单相同的成品卷。"))
			allocation = current
			current_identity = (source.current_finished_item_code, source.current_finished_batch_no)
			if identity and current_identity != identity:
				frappe.throw(_("同一张转客户单只能选择当前成品物料和批次相同的成品卷。"))
			identity = current_identity
			for fieldname in ("piece_no", "weight", "yard_qty", "finished_grade", "quality_flag", "grey_fabric_batch", "source_packing_receipt", "finished_batch_no", "roll_no"):
				row.set(fieldname, source.get(fieldname))
			row.source_finished_item_code = source.current_finished_item_code
		if allocation:
			self.source_customer, self.source_sales_order, self.source_sales_order_item = allocation
			self.source_customer_name = frappe.db.get_value("Customer", self.source_customer, "customer_name") or self.source_customer
		if identity:
			self.source_finished_item_code, self.source_finished_batch_no = identity

	def _ensure_target_batch(self):
		if self.finished_item_code == self.source_finished_item_code:
			return self.source_finished_batch_no
		if self.finished_batch_no and frappe.db.get_value("Batch", self.finished_batch_no, "item") == self.finished_item_code:
			return self.finished_batch_no
		date = getdate(self.transfer_date or nowdate())
		prefix = f"CPZ{date:%y%m%d}"
		batch_no = f"{prefix}{getseries(prefix, 3)}"
		frappe.get_doc({"doctype":"Batch", "batch_id":batch_no, "item":self.finished_item_code,
			"manufacturing_date":self.transfer_date, "description":_("成品转客户单：{0}").format(self.name)}).insert(ignore_permissions=True)
		self.db_set("finished_batch_no", batch_no, update_modified=False)
		self.finished_batch_no = batch_no
		return batch_no

	def _create_stock_entry(self):
		if self.stock_entry or self.finished_item_code == self.source_finished_item_code:
			self.finished_batch_no = self.source_finished_batch_no
			return
		if not frappe.db.exists("Warehouse", self.source_warehouse):
			frappe.throw(_("未找到成品仓库：{0}").format(self.source_warehouse))
		batch_no = self._ensure_target_batch()
		company = frappe.db.get_value("Warehouse", self.source_warehouse, "company")
		common = {"qty":flt(self.total_weight), "uom":get_setting("weight_uom"), "use_serial_batch_fields":1,
			"custom_roll_count":self.total_roll_count, "custom_yard_qty":self.total_yard_qty,
			"custom_yard_uom":get_setting("yard_uom"), "custom_production_flow_card":self.production_flow_card,
			"custom_finished_product_customer_transfer":self.name}
		entry = frappe.get_doc({"doctype":"Stock Entry", "stock_entry_type":"Repack", "purpose":"Repack",
			"company":company, "posting_date":self.transfer_date, "custom_finished_product_customer_transfer":self.name,
			"remarks":_("成品转客户单：{0}；{1} 转为 {2}").format(self.name, self.source_customer_name, self.target_customer_name),
			"items":[
				{**common, "item_code":self.source_finished_item_code, "s_warehouse":self.source_warehouse, "batch_no":self.source_finished_batch_no},
				{**common, "item_code":self.finished_item_code, "t_warehouse":self.source_warehouse, "batch_no":batch_no, "allow_zero_valuation_rate":1},
			]})
		entry.insert(ignore_permissions=True)
		entry.submit()
		self.db_set("stock_entry", entry.name, update_modified=False)

	def _set_totals(self):
		self.total_roll_count = len(self.items or [])
		self.total_weight = sum(flt(row.weight) for row in self.items or [])
		self.total_yard_qty = sum(flt(row.yard_qty) for row in self.items or [])

	def _record_progress(self):
		description = _(
			"转客户 {0} 匹，{1} Kg，{2} Y；客户：{3} → {4}；销售订单：{5} → {6}；"
			"成品物料：{7} → {8}；成品批次：{9} → {10}；库存凭证：{11}"
		).format(
			self.total_roll_count, self.total_weight, self.total_yard_qty,
			self.source_customer_name or self.source_customer, self.target_customer_name or self.target_customer,
			self.source_sales_order or "-", self.target_sales_order or "-",
			self.source_finished_item_code or "-", self.finished_item_code or "-",
			self.source_finished_batch_no or "-", self.finished_batch_no or "-", self.stock_entry or "-",
		)
		record_production_progress(
			self.production_flow_card, "成品转客户", "成品部分转客户", self.doctype, self.name,
			batch_no=self.finished_batch_no, quantity=self.total_weight, uom=get_setting("weight_uom"),
			roll_count=self.total_roll_count, yard_qty=self.total_yard_qty, description=description,
		)


def _packing_header(flow_card):
	return frappe.db.get_value(
		"Finished Product Packing Receipt",
		{"production_flow_card": flow_card, "docstatus": 1, "packing_status": "已入库"},
		["sales_order", "sales_order_item", "customer", "customer_name", "finished_item_code", "finished_batch_no", "finished_product_name", "finished_specification", "color_no", "color", "target_warehouse"],
		as_dict=True,
	)


def _packing_item(name):
	rows = frappe.db.sql(
		"""SELECT item.name, item.roll_no, item.piece_no, item.weight, item.yard_qty,
			item.finished_grade, item.quality_flag, item.grey_fabric_batch, item.warehouse_status,
			parent.name AS source_packing_receipt, parent.production_flow_card,
			COALESCE(NULLIF(item.current_finished_item_code, ''), parent.finished_item_code) AS current_finished_item_code,
			COALESCE(NULLIF(item.current_finished_batch_no, ''), parent.finished_batch_no) AS current_finished_batch_no,
			COALESCE(NULLIF(item.current_finished_batch_no, ''), parent.finished_batch_no) AS finished_batch_no,
			COALESCE(NULLIF(item.current_customer, ''), parent.customer) AS allocated_customer,
			COALESCE(NULLIF(item.current_customer_name, ''), parent.customer_name) AS allocated_customer_name,
			COALESCE(NULLIF(item.current_sales_order, ''), parent.sales_order) AS allocated_sales_order,
			COALESCE(NULLIF(item.current_sales_order_item, ''), parent.sales_order_item) AS allocated_sales_order_item
		FROM `tabFinished Product Packing Receipt Item` item
		INNER JOIN `tabFinished Product Packing Receipt` parent ON parent.name=item.parent
		WHERE item.name=%s AND parent.docstatus=1 AND parent.packing_status='已入库'""",
		name, as_dict=True,
	)
	return rows[0] if rows else None


def _previous_transfer(packing_item, excluding):
	return frappe.db.get_value(
		"Finished Product Customer Transfer Item",
		{"packing_receipt_item": packing_item, "parent": ["!=", excluding], "docstatus": 1}, "parent",
		order_by="creation desc",
	)


def _finished_item_details(item_code):
	return frappe.db.get_value("Item", item_code,
		["item_name", "custom_finished_specification as finished_specification",
		 "custom_finished_color_no as color_no", "custom_finished_color as color"], as_dict=True) or frappe._dict()


def get_available_rolls(flow_card):
	if not flow_card:
		return []
	return frappe.db.sql(
		"""SELECT item.name, item.roll_no, item.piece_no, item.weight, item.yard_qty,
			item.finished_grade, item.quality_flag, item.grey_fabric_batch,
			parent.name AS source_packing_receipt,
			COALESCE(NULLIF(item.current_finished_item_code, ''), parent.finished_item_code) AS current_finished_item_code,
			COALESCE(NULLIF(item.current_finished_batch_no, ''), parent.finished_batch_no) AS current_finished_batch_no,
			COALESCE(NULLIF(item.current_finished_batch_no, ''), parent.finished_batch_no) AS finished_batch_no,
			COALESCE(NULLIF(item.current_customer, ''), parent.customer) AS allocated_customer,
			COALESCE(NULLIF(item.current_customer_name, ''), parent.customer_name) AS allocated_customer_name,
			COALESCE(NULLIF(item.current_sales_order, ''), parent.sales_order) AS allocated_sales_order,
			COALESCE(NULLIF(item.current_sales_order_item, ''), parent.sales_order_item) AS allocated_sales_order_item
		FROM `tabFinished Product Packing Receipt Item` item
		INNER JOIN `tabFinished Product Packing Receipt` parent ON parent.name=item.parent
		WHERE parent.production_flow_card=%(flow_card)s AND parent.docstatus=1
			AND parent.packing_status='已入库' AND item.warehouse_status='已入库'
			AND NOT EXISTS (
				SELECT 1 FROM `tabFinished Product Delivery Item` delivery
				WHERE delivery.packing_receipt_item=item.name AND delivery.docstatus=1
			)
		ORDER BY parent.packing_date, parent.creation, item.idx""",
		{"flow_card": flow_card}, as_dict=True,
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_flow_cards_with_finished_stock(doctype, txt, searchfield, start, page_len, filters=None):
	"""只返回尚有可用成品库存的生产流转卡。

	可用数量以卷级库存状态为准，并要求剩余总重量大于 0 Kg。
	"""
	txt = f"%{txt or ''}%"
	return frappe.db.sql(
		"""SELECT card.name,
			MAX(COALESCE(NULLIF(item.current_customer_name, ''), packing.customer_name)) AS customer_name,
			MAX(packing.finished_product_name) AS finished_product_name,
			COUNT(DISTINCT item.name) AS available_roll_count,
			ROUND(SUM(COALESCE(item.weight, 0)), 3) AS available_weight
		FROM `tabProduction Flow Card` card
		INNER JOIN `tabFinished Product Packing Receipt` packing
			ON packing.production_flow_card=card.name
			AND packing.docstatus=1 AND packing.packing_status='已入库'
		INNER JOIN `tabFinished Product Packing Receipt Item` item
			ON item.parent=packing.name AND item.warehouse_status='已入库'
		WHERE card.docstatus=1
			AND NOT EXISTS (
				SELECT 1 FROM `tabFinished Product Delivery Item` delivery
				WHERE delivery.packing_receipt_item=item.name AND delivery.docstatus=1
			)
			AND (card.name LIKE %(txt)s OR packing.customer_name LIKE %(txt)s
				OR packing.finished_product_name LIKE %(txt)s)
		GROUP BY card.name
		HAVING SUM(COALESCE(item.weight, 0)) > 0
		ORDER BY card.modified DESC
		LIMIT %(start)s, %(page_len)s""",
		{"txt": txt, "start": cint(start), "page_len": cint(page_len)},
	)


@frappe.whitelist()
def get_transfer_flow_card_details(flow_card):
	packing = _packing_header(flow_card)
	if not packing:
		frappe.throw(_("该生产流转卡尚无已入库成品。"))
	rows = get_available_rolls(flow_card)
	available_weight = sum(flt(row.weight) for row in rows)
	if not rows or available_weight <= 0:
		frappe.throw(_("该生产流转卡已无可转客户的成品库存。"))
	packing.available_roll_count = len(rows)
	packing.available_weight = available_weight
	first = rows[0]
	group_key = (
		first.allocated_customer, first.allocated_sales_order, first.allocated_sales_order_item,
		first.current_finished_item_code, first.current_finished_batch_no,
	)
	packing.auto_import_rolls = [row for row in rows if (
		row.allocated_customer, row.allocated_sales_order, row.allocated_sales_order_item,
		row.current_finished_item_code, row.current_finished_batch_no,
	) == group_key]
	packing.skipped_roll_count = len(rows) - len(packing.auto_import_rolls)
	return packing


def _same_product_value(source, target):
	source = str(source or "").strip()
	target = str(target or "").strip()
	return not source or not target or source == target


@frappe.whitelist()
def get_target_sales_order_details(
	sales_order, finished_product_name=None, finished_specification=None, color_no=None, color=None
):
	"""返回新销售订单的客户和与当前成品匹配的明细。"""
	order = frappe.get_doc("Dyeing Sales Order", sales_order)
	order.check_permission("read")
	if order.docstatus != 1:
		frappe.throw(_("新染整销售订单必须已提交。"))
	items = []
	for row in order.items:
		matched = all((
			_same_product_value(finished_product_name, row.finished_product_name),
			_same_product_value(finished_specification, row.finished_specification),
			_same_product_value(color_no, row.color_no),
			_same_product_value(color, row.color),
		))
		items.append({
			"name": row.name,
			"grey_fabric_batch": row.grey_fabric_batch,
			"item_name": row.item_name,
			"finished_product_name": row.finished_product_name,
			"finished_specification": row.finished_specification,
			"color_no": row.color_no,
			"color": row.color,
			"qty": row.qty,
			"uom": row.uom,
			"matched": matched,
		})
	matched_items = [row for row in items if row["matched"]]
	if len(items) == 1:
		matched_items = items
	return {
		"customer": order.customer,
		"customer_name": order.customer_name
			or frappe.db.get_value("Customer", order.customer, "customer_name")
			or order.customer,
		"items": items,
		"matched_items": matched_items,
	}


@frappe.whitelist()
def get_target_sales_order_item_details(sales_order_item):
	row = frappe.db.get_value("Dyeing Sales Order Item", sales_order_item,
		["parent", "finished_product_name", "finished_specification", "color_no", "color"], as_dict=True)
	if not row:
		frappe.throw(_("未找到新染整销售订单明细。"))
	return row


def handle_stock_entry_cancel(doc, method=None):
	if not doc.get("custom_finished_product_customer_transfer") or doc.flags.from_finished_product_customer_transfer:
		return
	transfer = frappe.get_doc("Finished Product Customer Transfer", doc.custom_finished_product_customer_transfer)
	if transfer.docstatus == 1:
		frappe.throw(_("请通过成品转客户单 {0} 执行取消。").format(transfer.name))


@frappe.whitelist()
def get_available_customer_transfer_rolls(doctype, txt, searchfield, start, page_len, filters, as_dict=False, **kwargs):
	filters = frappe.parse_json(filters) or {}
	excluded = set(frappe.parse_json(filters.get("excluded_names") or "[]") or [])
	rows = [row for row in get_available_rolls(filters.get("production_flow_card")) if row.name not in excluded]
	txt = (txt or "").lower()
	rows = [row for row in rows if not txt or txt in (row.roll_no or "").lower() or txt in (row.source_packing_receipt or "").lower() or txt in (row.allocated_customer_name or "").lower()]
	rows = rows[cint(start):cint(start) + cint(page_len)]
	if as_dict:
		return [{"name": row.name, "匹号": row.piece_no, "重量(Kg)": row.weight, "码数(Y)": row.yard_qty, "当前客户": row.allocated_customer_name, "成品卷号": row.roll_no, "来源包装入库单": row.source_packing_receipt} for row in rows]
	return [[row.name, row.piece_no, row.weight, row.yard_qty, row.allocated_customer_name, row.roll_no, row.source_packing_receipt] for row in rows]


@frappe.whitelist()
def get_customer_transfer_roll_details(names):
	names = frappe.parse_json(names) or []
	return [row for name in names if (row := _packing_item(name))]


def refresh_customer_transfer_progress(flow_card):
	"""Recalculate the latest logistics progress without changing production status."""
	if not flow_card or not frappe.db.exists("Production Flow Card", flow_card):
		return
	counts = frappe.db.sql(
		"""SELECT COUNT(*) AS available_count,
			SUM(CASE WHEN transfer.docstatus=1 THEN 1 ELSE 0 END) AS transferred_count
		FROM `tabFinished Product Packing Receipt Item` item
		INNER JOIN `tabFinished Product Packing Receipt` packing ON packing.name=item.parent
		LEFT JOIN `tabFinished Product Customer Transfer` transfer ON transfer.name=item.customer_transfer
		WHERE packing.production_flow_card=%s AND packing.docstatus=1
			AND packing.packing_status='已入库' AND item.warehouse_status='已入库'""",
		flow_card, as_dict=True,
	)[0]
	available_count = cint(counts.available_count)
	transferred_count = cint(counts.transferred_count)
	if transferred_count:
		production_status = frappe.db.get_value("Production Flow Card", flow_card, "production_status")
		status = (
			"成品全部转客户"
			if production_status == "已完成" and available_count and transferred_count == available_count
			else "成品部分转客户"
		)
		latest = frappe.db.sql(
			"""SELECT progress.name, progress.progress_time, progress.source_document
			FROM `tabProduction Flow Card Progress` progress
			INNER JOIN `tabFinished Product Customer Transfer` transfer
				ON transfer.name=progress.source_document AND transfer.docstatus=1
			WHERE progress.parent=%s AND progress.source_doctype='Finished Product Customer Transfer'
			ORDER BY progress.progress_time DESC, progress.creation DESC LIMIT 1""",
			flow_card, as_dict=True,
		)
		if latest:
			frappe.db.set_value("Production Flow Card Progress", latest[0].name, "progress_status", status, update_modified=False)
			frappe.db.set_value("Production Flow Card", flow_card, {
				"current_progress_status": status,
				"latest_progress_time": latest[0].progress_time,
				"latest_source_doctype": "Finished Product Customer Transfer",
				"latest_source_document": latest[0].source_document,
			}, update_modified=False)
		return

	if frappe.db.count("Finished Product Delivery", {"production_flow_card": flow_card, "docstatus": 1}):
		from dyeing_finishing.dyeing_finishing.doctype.finished_product_delivery.finished_product_delivery import refresh_delivery_progress
		refresh_delivery_progress(flow_card)
		return

	from dyeing_finishing.dyeing_finishing.doctype.finished_product_packing_receipt.finished_product_packing_receipt import refresh_packing_progress_summary
	refresh_packing_progress_summary(flow_card)

