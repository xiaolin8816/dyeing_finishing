from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import getseries
from frappe.utils import cint, flt, getdate, now_datetime, nowdate
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry

from dyeing_finishing.dyeing_finishing.doctype.production_flow_card.production_flow_card import (
	ensure_flow_card_open,
	record_production_progress,
	remove_production_progress,
)
from dyeing_finishing.dyeing_finishing.item import get_or_create_finished_item
from dyeing_finishing.dyeing_finishing.settings import get_setting


class FinishedProductPackingReceipt(Document):
	def autoname(self):
		date = getdate(self.packing_date or nowdate())
		prefix = f"BZ{date:%y%m%d}"
		self.name = f"{prefix}{getseries(prefix, 3)}"

	def before_insert(self):
		self.packing_receipt_no = self.name
		self.packing_date = self.packing_date or getdate(nowdate())
		self.packing_status = self.packing_status or "保存"

	def validate(self):
		self.packing_receipt_no = self.name
		self.packing_date = self.packing_date or getdate(nowdate())
		self.source_warehouse = get_setting("production_transit_warehouse")
		self.target_warehouse = self.target_warehouse or get_setting("finished_product_warehouse")
		self.generate_stock_entry = 1
		self._set_flow_card_details()
		self._validate_items()
		self._set_totals()

	def on_update(self):
		if self.docstatus != 0:
			return
		started_at = self.packing_started_at or now_datetime()
		self.db_set(
			{
				"packing_status": "包装中",
				"packing_operator": self.packing_operator or frappe.session.user,
				"packing_started_at": started_at,
			},
			update_modified=False,
		)
		self.packing_status = "包装中"
		self.packing_operator = self.packing_operator or frappe.session.user
		self.packing_started_at = started_at
		self._upsert_packing_progress("成品包装中")

	def before_submit(self):
		self._validate_items()
		self._set_totals()
		self._validate_partial_packing_policy()
		self.packing_operator = self.packing_operator or frappe.session.user
		self.packing_started_at = self.packing_started_at or now_datetime()
		self.packing_completed_at = now_datetime()
		self.packing_status = "已包装"

	def _validate_partial_packing_policy(self):
		if cint(get_setting("allow_partial_packing")):
			return
		other_receipt = frappe.db.get_value(
			"Finished Product Packing Receipt",
			{"production_flow_card": self.production_flow_card, "name": ["!=", self.name], "docstatus": ["<", 2]},
			"name",
		)
		if other_receipt:
			frappe.throw(_("系统设置不允许分批包装，该流转卡已有包装入库单 {0}").format(other_receipt))
		batches = {row.grey_fabric_batch for row in self.items if row.grey_fabric_batch}
		remaining = sum(flt(stock.qty) for batch in batches if (stock := _transit_batch_stock(batch)))
		if self.total_grey_fabric_qty + 0.000001 < remaining:
			frappe.throw(_("系统设置不允许分批包装，本次必须结转当前流转卡的全部剩余胚布。"))

	def on_submit(self):
		self._create_stock_entry()
		self.db_set(
			{
				"packing_status": "已入库",
				"warehouse_date": self.packing_date,
				"warehouse_operator": frappe.session.user,
			},
			update_modified=False,
		)
		for row in self.items:
			row.db_set("warehouse_status", "已入库", update_modified=False)
		self._upsert_packing_progress("成品已入库")

	def on_cancel(self):
		stock_entry = self.stock_entry
		if stock_entry:
			self.db_set("stock_entry", None, update_modified=False)
			entry = frappe.get_doc("Stock Entry", stock_entry)
			if entry.docstatus == 1:
				# BEAM's Stock Entry override calls make_sl_entries twice on cancel
				# whenever Handling Units are enabled, even when this entry has no
				# handling-unit rows.  Use ERPNext's stock-ledger implementation for
				# packaging entries to avoid subtracting the batch quantity twice.
				entry.update_stock_ledger = StockEntry.update_stock_ledger.__get__(entry, entry.__class__)
				entry.flags.from_finished_packing_receipt = True
				entry.cancel()
		self.db_set(
			{
				"packing_status": "已取消",
				"warehouse_date": None,
				"warehouse_operator": None,
			},
			update_modified=False,
		)
		for row in self.items:
			row.db_set("warehouse_status", "已取消", update_modified=False)
		self._upsert_packing_progress("成品入库已取消")

	def on_trash(self):
		remove_production_progress(self.doctype, self.name)

	def after_delete(self):
		refresh_packing_progress_summary(self.production_flow_card)

	def _set_flow_card_details(self):
		if not self.production_flow_card:
			frappe.throw(_("请选择生产流转卡"))
		card = frappe.get_doc("Production Flow Card", self.production_flow_card)
		ensure_flow_card_open(card)
		self.sales_order = card.sales_order
		self.sales_order_item = card.sales_order_item
		self.customer = card.customer
		self.customer_name = frappe.db.get_value("Customer", card.customer, "customer_name") or card.customer
		self.color_no = card.color_no
		self.color = card.color
		self.finished_product_name = card.finished_product_name
		self.finished_width = card.finished_width
		self.finished_gsm = card.finished_gsm
		self.finished_specification = card.finished_specification
		self.finished_uom = get_setting("weight_uom")
		self.order_qty = card.order_qty
		self.process_type = self.process_type or card.process_type
		self.process_requirements = "；".join(
			row.process_requirement_name for row in card.process_requirements if row.process_requirement_name
		)
		self.packaging_requirements = "；".join(
			row.packaging_requirement_name for row in card.packaging_requirements if row.packaging_requirement_name
		)
		self.production_operations = "；".join(
			row.operation_name for row in card.operations if row.operation_name
		)
		issues = _flow_card_issue_rows(card.name)
		self.grey_fabric_batches = "；".join(dict.fromkeys(row.batch_no for row in issues if row.batch_no))
		self.grey_fabric_issue_qty = sum(flt(row.issue_qty) for row in issues)
		self.finished_item_code = get_or_create_finished_item(
			card.color_no,
			card.finished_product_name,
			card.finished_width,
			card.finished_gsm,
		)

	def _validate_items(self):
		if not self.items:
			frappe.throw(_("请至少填写一条成品包装明细"))
		piece_start = frappe.db.sql(
			"""SELECT COALESCE(MAX(item.piece_no), 0)
			FROM `tabFinished Product Packing Receipt Item` item
			INNER JOIN `tabFinished Product Packing Receipt` parent ON parent.name = item.parent
			WHERE parent.production_flow_card = %s AND parent.name != %s AND parent.docstatus < 2""",
			(self.production_flow_card, self.name),
		)[0][0]
		allowed_batches = {row.batch_no for row in _flow_card_issue_rows(self.production_flow_card) if row.batch_no}
		seen_rolls = set()
		batch_qty = defaultdict(float)
		prefix = "FP" + "".join(character for character in self.production_flow_card if character.isalnum())
		for index, row in enumerate(self.items, 1):
			row.piece_no = int(piece_start) + index
			row.weight_uom = get_setting("weight_uom")
			row.yard_uom = get_setting("yard_uom")
			row.warehouse_status = row.warehouse_status or "未入库"
			row.roll_no = f"{prefix}-{row.piece_no:03d}"
			row.barcode = row.roll_no
			if row.roll_no in seen_rolls:
				frappe.throw(_("成品卷号重复：{0}").format(row.roll_no))
			seen_rolls.add(row.roll_no)
			if row.grey_fabric_batch not in allowed_batches:
				frappe.throw(_("第 {0} 行胚布批次不属于当前生产流转卡").format(row.idx))
			if flt(row.grey_fabric_qty) <= 0:
				frappe.throw(_("第 {0} 行胚布结转重量必须大于 0").format(row.idx))
			if flt(row.weight) <= 0:
				frappe.throw(_("第 {0} 行成品重量必须大于 0").format(row.idx))
			if flt(row.yard_qty) <= 0:
				frappe.throw(_("第 {0} 行码数必须大于 0").format(row.idx))
			duplicate = frappe.db.get_value(
				"Finished Product Packing Receipt Item",
				{"roll_no": row.roll_no, "parent": ["!=", self.name]},
				"parent",
			)
			if duplicate:
				frappe.throw(_("成品卷号 {0} 已在包装单 {1} 使用").format(row.roll_no, duplicate))
			batch_qty[row.grey_fabric_batch] += flt(row.grey_fabric_qty)

		for batch_no, quantity in batch_qty.items():
			stock = _transit_batch_stock(batch_no)
			if not stock or quantity > flt(stock.qty):
				available = flt(stock.qty) if stock else 0
				frappe.throw(_("批次 {0} 的胚布结转重量 {1} Kg 超过生产中转仓库存 {2} Kg").format(batch_no, quantity, available))

	def _set_totals(self):
		self.total_roll_count = len(self.items or [])
		self.total_weight = sum(flt(row.weight) for row in self.items or [])
		self.total_yard_qty = sum(flt(row.yard_qty) for row in self.items or [])
		self.total_grey_fabric_qty = sum(flt(row.grey_fabric_qty) for row in self.items or [])
		self.weight_difference = self.total_weight - self.total_grey_fabric_qty
		self.weight_difference_rate = (
			self.weight_difference / self.total_grey_fabric_qty * 100 if self.total_grey_fabric_qty else 0
		)

	def _ensure_finished_batch(self):
		batch_id = f"CP-{self.production_flow_card}"
		if frappe.db.exists("Batch", batch_id):
			batch = frappe.get_doc("Batch", batch_id)
			if batch.item != self.finished_item_code:
				frappe.throw(_("成品批次 {0} 已属于其他物料").format(batch_id))
		else:
			batch = frappe.get_doc(
				{
					"doctype": "Batch",
					"batch_id": batch_id,
					"item": self.finished_item_code,
					"manufacturing_date": self.packing_date,
					"description": _("生产流转卡：{0}").format(self.production_flow_card),
				}
			)
			batch.insert(ignore_permissions=True)
		self.finished_batch_no = batch.name
		return batch.name

	def _create_stock_entry(self):
		if self.stock_entry:
			return
		source_warehouse = get_setting("production_transit_warehouse")
		for warehouse in (source_warehouse, self.target_warehouse):
			if not frappe.db.exists("Warehouse", warehouse):
				frappe.throw(_("未找到仓库：{0}").format(warehouse))
		company = frappe.db.get_value("Warehouse", self.target_warehouse, "company")
		if not company:
			frappe.throw(_("目标仓库未设置公司"))
		batch_totals = defaultdict(float)
		for row in self.items:
			batch_totals[row.grey_fabric_batch] += flt(row.grey_fabric_qty)
		stock_items = []
		for batch_no, quantity in batch_totals.items():
			stock = _transit_batch_stock(batch_no)
			stock_items.append(
				{
					"item_code": stock.item_code,
					"qty": quantity,
					"uom": frappe.db.get_value("Item", stock.item_code, "stock_uom"),
					"s_warehouse": source_warehouse,
					"batch_no": batch_no,
					"use_serial_batch_fields": 1,
					"allow_zero_valuation_rate": 1,
					"custom_production_flow_card": self.production_flow_card,
					"custom_finished_packing_receipt": self.name,
				}
			)
		finished_batch = self._ensure_finished_batch()
		stock_items.append(
			{
				"item_code": self.finished_item_code,
				"qty": flt(self.total_weight),
				"uom": get_setting("weight_uom"),
				"t_warehouse": self.target_warehouse,
				"batch_no": finished_batch,
				"use_serial_batch_fields": 1,
				"allow_zero_valuation_rate": 1,
				"custom_roll_count": flt(self.total_roll_count),
				"custom_yard_qty": flt(self.total_yard_qty),
				"custom_yard_uom": get_setting("yard_uom"),
				"custom_production_flow_card": self.production_flow_card,
				"custom_finished_packing_receipt": self.name,
			}
		)
		entry = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Repack",
				"purpose": "Repack",
				"company": company,
				"posting_date": self.packing_date,
				"from_warehouse": source_warehouse,
				"to_warehouse": self.target_warehouse,
				"custom_finished_packing_receipt": self.name,
				"remarks": _("成品包装入库单：{0}；生产流转卡：{1}").format(self.name, self.production_flow_card),
				"items": stock_items,
			}
		)
		entry.insert(ignore_permissions=True)
		entry.submit()
		self.db_set({"stock_entry": entry.name, "finished_batch_no": finished_batch}, update_modified=False)

	def _upsert_packing_progress(self, status):
		progress_time = now_datetime()
		description = _("包装 {0} 匹，{1} Kg，{2} Y").format(
			self.total_roll_count, self.total_weight, self.total_yard_qty
		)
		batches = list(dict.fromkeys(row.grey_fabric_batch for row in self.items if row.grey_fabric_batch))
		batch_no = self.finished_batch_no or (batches[0] if len(batches) == 1 else "")
		filters = {
			"parent": self.production_flow_card,
			"source_doctype": self.doctype,
			"source_document": self.name,
		}
		progress_name = frappe.db.get_value("Production Flow Card Progress", filters, "name")
		if not progress_name:
			record_production_progress(
				self.production_flow_card,
				"成品包装入库",
				status,
				self.doctype,
				self.name,
				batch_no=batch_no,
				quantity=self.total_weight,
				uom=get_setting("weight_uom"),
				description=description,
				roll_count=self.total_roll_count,
				yard_qty=self.total_yard_qty,
			)
		else:
			frappe.db.set_value(
				"Production Flow Card Progress",
				progress_name,
				{
					"progress_time": progress_time,
					"progress_status": status,
					"batch_no": batch_no,
					"roll_count": self.total_roll_count,
					"quantity": self.total_weight,
					"uom": get_setting("weight_uom"),
					"yard_qty": self.total_yard_qty,
					"operator": frappe.session.user,
					"description": description,
				},
				update_modified=False,
			)
			frappe.db.set_value(
				"Production Flow Card",
				self.production_flow_card,
				{
					"current_progress_status": status,
					"latest_progress_time": progress_time,
					"latest_source_doctype": self.doctype,
					"latest_source_document": self.name,
				},
				update_modified=False,
			)
		refresh_packing_progress_summary(self.production_flow_card, fallback_status=status)

def _flow_card_issue_rows(flow_card):
	return frappe.db.sql(
		"""SELECT item.batch_no, item.item_code, item.issue_qty
		FROM `tabGrey Fabric Issue Item` item
		INNER JOIN `tabGrey Fabric Issue` parent ON parent.name = item.parent
		WHERE parent.flow_card = %s AND parent.docstatus = 1 AND item.batch_no IS NOT NULL""",
		flow_card,
		as_dict=True,
	)


def _transit_batch_stock(batch_no):
	rows = frappe.db.sql(
		"""SELECT sle.item_code,
			COALESCE(SUM(CASE WHEN COALESCE(NULLIF(sle.batch_no, ''), bundle.batch_no) = %(batch_no)s
				THEN sle.actual_qty ELSE 0 END), 0) AS qty
		FROM `tabStock Ledger Entry` sle
		LEFT JOIN `tabSerial and Batch Entry` bundle ON bundle.parent = sle.serial_and_batch_bundle
		WHERE sle.warehouse = %(warehouse)s AND sle.is_cancelled = 0
		GROUP BY sle.item_code
		HAVING qty > 0
		LIMIT 1""",
		{"batch_no": batch_no, "warehouse": get_setting("production_transit_warehouse")},
		as_dict=True,
	)
	return rows[0] if rows else None


def refresh_packing_progress_summary(flow_card, fallback_status=None):
	"""Refresh the cumulative packing picture shown on a production flow card."""
	if not flow_card or not frappe.db.exists("Production Flow Card", flow_card):
		return

	submitted = frappe.db.sql(
		"""SELECT COUNT(*) AS receipt_count,
			COALESCE(SUM(total_roll_count), 0) AS roll_count,
			COALESCE(SUM(total_weight), 0) AS weight,
			COALESCE(SUM(total_yard_qty), 0) AS yard_qty
		FROM `tabFinished Product Packing Receipt`
		WHERE production_flow_card = %s
			AND docstatus = 1
			AND packing_status = '已入库'""",
		flow_card,
		as_dict=True,
	)[0]
	in_progress_weight = flt(
		frappe.db.sql(
			"""SELECT COALESCE(SUM(total_weight), 0)
			FROM `tabFinished Product Packing Receipt`
			WHERE production_flow_card = %s
				AND docstatus = 0
				AND packing_status = '包装中'""",
			flow_card,
		)[0][0]
	)
	issues = _flow_card_issue_rows(flow_card)
	issued_qty = sum(flt(row.issue_qty) for row in issues)
	batches = {row.batch_no for row in issues if row.batch_no}
	remaining_qty = sum(flt((_transit_batch_stock(batch) or {}).get("qty")) for batch in batches)
	completion_rate = min(max((issued_qty - remaining_qty) / issued_qty * 100, 0), 100) if issued_qty else 0
	delivery_count = frappe.db.count(
		"Finished Product Delivery", {"production_flow_card": flow_card, "docstatus": 1}
	)
	available_roll_count = frappe.db.sql(
		"""SELECT COUNT(*)
		FROM `tabFinished Product Packing Receipt Item` item
		INNER JOIN `tabFinished Product Packing Receipt` parent ON parent.name = item.parent
		WHERE parent.production_flow_card = %s
			AND parent.docstatus = 1 AND parent.packing_status = '已入库'
			AND item.warehouse_status = '已入库'""",
		flow_card,
	)[0][0]
	is_completed = bool(
		issued_qty
		and submitted.receipt_count
		and remaining_qty <= 0.000001
		and in_progress_weight <= 0.000001
	)

	if delivery_count:
		progress_status = "成品全部出库" if is_completed and not available_roll_count else "成品部分出库"
	elif in_progress_weight > 0:
		progress_status = "成品包装中"
	elif issued_qty and remaining_qty <= 0.000001 and submitted.receipt_count:
		progress_status = "成品全部入库"
	elif submitted.receipt_count:
		progress_status = "成品部分入库"
	else:
		progress_status = fallback_status

	values = {
		"packing_receipt_count": submitted.receipt_count,
		"packed_roll_count": submitted.roll_count,
		"packed_weight": submitted.weight,
		"packed_yard_qty": submitted.yard_qty,
		"packing_in_progress_weight": in_progress_weight,
		"packing_remaining_qty": remaining_qty,
		"packing_completion_rate": completion_rate,
	}
	current_production_status = frappe.db.get_value("Production Flow Card", flow_card, "production_status")
	if current_production_status != "已关闭":
		values["production_status"] = "已完成" if is_completed else "进行中"
	if progress_status:
		values["current_progress_status"] = progress_status
	frappe.db.set_value("Production Flow Card", flow_card, values, update_modified=False)


@frappe.whitelist()
def get_packing_flow_card_details(flow_card):
	card = frappe.get_doc("Production Flow Card", flow_card)
	ensure_flow_card_open(card)
	issues = _flow_card_issue_rows(card.name)
	return {
		"sales_order": card.sales_order,
		"sales_order_item": card.sales_order_item,
		"customer": card.customer,
		"customer_name": frappe.db.get_value("Customer", card.customer, "customer_name") or card.customer,
		"color_no": card.color_no,
		"color": card.color,
		"finished_product_name": card.finished_product_name,
		"finished_width": card.finished_width,
		"finished_gsm": card.finished_gsm,
		"finished_specification": card.finished_specification,
		"finished_uom": get_setting("weight_uom"),
		"order_qty": card.order_qty,
		"process_type": card.process_type,
		"process_requirements": "；".join(row.process_requirement_name for row in card.process_requirements if row.process_requirement_name),
		"packaging_requirements": "；".join(row.packaging_requirement_name for row in card.packaging_requirements if row.packaging_requirement_name),
		"production_operations": "；".join(row.operation_name for row in card.operations if row.operation_name),
		"grey_fabric_batches": list(dict.fromkeys(row.batch_no for row in issues if row.batch_no)),
		"grey_fabric_issue_qty": sum(flt(row.issue_qty) for row in issues),
	}


def handle_stock_entry_cancel(doc, method=None):
	if not doc.get("custom_finished_packing_receipt") or doc.flags.from_finished_packing_receipt:
		return
	packing = frappe.get_doc("Finished Product Packing Receipt", doc.custom_finished_packing_receipt)
	if packing.docstatus != 1:
		return
	packing.db_set(
		{
			"packing_status": "已包装",
			"stock_entry": None,
			"warehouse_date": None,
			"warehouse_operator": None,
		},
		update_modified=False,
	)
	for row in packing.items:
		row.db_set("warehouse_status", "未入库", update_modified=False)
	packing._upsert_packing_progress("成品入库凭证已取消，等待重新入库")
