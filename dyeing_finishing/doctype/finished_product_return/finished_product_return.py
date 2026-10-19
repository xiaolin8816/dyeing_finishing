import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import getseries
from frappe.utils import flt, getdate, nowdate
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry

from dyeing_finishing.dyeing_finishing.doctype.production_flow_card.production_flow_card import (
	record_production_progress,
	remove_production_progress,
)
from dyeing_finishing.dyeing_finishing.settings import get_setting


EPSILON = 0.000001


class FinishedProductReturn(Document):
	def autoname(self):
		date = getdate(self.return_date or nowdate())
		prefix = f"TH{date:%y%m%d}"
		self.name = f"{prefix}{getseries(prefix, 3)}"

	def before_insert(self):
		self.return_no = self.name
		self.return_date = self.return_date or getdate(nowdate())
		self.return_status = "保存"

	def validate(self):
		self.return_no = self.name
		self.return_date = self.return_date or getdate(nowdate())
		self.target_warehouse = get_setting("finished_product_return_warehouse")
		self._set_flow_card_details()
		self._validate_and_refresh_items()
		self._set_totals()
		self._set_delivery_summary()

	def before_submit(self):
		self._validate_and_refresh_items()
		self._set_totals()
		self._validate_target_warehouse()

	def on_submit(self):
		self._create_stock_entry()
		self.db_set({
			"return_status": "已收货待检", "received_by": frappe.session.user,
			"received_date": getdate(nowdate()),
		}, update_modified=False)
		for row in self.items:
			refresh_roll_return_status(row.packing_receipt_item)
		self._record_progress("成品退货待处理")
		refresh_return_summaries(self.production_flow_card)

	def on_cancel(self):
		stock_entry = self.stock_entry
		if stock_entry:
			self.db_set("stock_entry", None, update_modified=False)
			entry = frappe.get_doc("Stock Entry", stock_entry)
			if entry.docstatus == 1:
				entry.update_stock_ledger = StockEntry.update_stock_ledger.__get__(entry, entry.__class__)
				entry.flags.from_finished_product_return = True
				entry.cancel()
		self.db_set("return_status", "已取消", update_modified=False)
		for row in self.items:
			refresh_roll_return_status(row.packing_receipt_item)
		self._record_progress("成品退货已取消")
		refresh_return_summaries(self.production_flow_card)

	def on_trash(self):
		remove_production_progress(self.doctype, self.name)

	def _set_flow_card_details(self):
		if not self.production_flow_card:
			frappe.throw(_("请选择生产流转卡"))
		card = frappe.db.get_value(
			"Production Flow Card", self.production_flow_card,
			["name", "docstatus", "sales_order", "customer", "finished_product_name",
			 "finished_specification", "color_no", "color"], as_dict=True,
		)
		if not card or card.docstatus != 1:
			frappe.throw(_("只能选择已提交的生产流转卡"))
		product = frappe.db.get_value(
			"Finished Product Delivery", {"production_flow_card": card.name, "docstatus": 1, "delivery_status": "已出库"},
			["sales_order", "customer", "customer_name", "finished_item_code", "finished_batch_no",
			 "finished_product_name", "finished_specification", "color_no", "color"], as_dict=True,
		)
		if not product:
			frappe.throw(_("生产流转卡 {0} 尚无已提交的成品出库记录").format(card.name))
		for fieldname in ("sales_order", "customer", "customer_name", "finished_item_code", "finished_batch_no",
			"finished_product_name", "finished_specification", "color_no", "color"):
			self.set(fieldname, product.get(fieldname) or card.get(fieldname))

	def _validate_and_refresh_items(self):
		if not self.items:
			frappe.throw(_("请至少选择一卷已出库成品"))
		seen = set()
		for row in self.items:
			if not row.source_delivery_item or row.source_delivery_item in seen:
				frappe.throw(_("退货明细存在重复成品卷"))
			seen.add(row.source_delivery_item)
			source = _returnable_delivery_item(row.source_delivery_item)
			if not source or source.production_flow_card != self.production_flow_card:
				frappe.throw(_("成品卷 {0} 不属于当前流转卡或来源出库单已失效").format(row.roll_no or row.source_delivery_item))
			if flt(source.remaining_weight) <= EPSILON or flt(source.remaining_yard_qty) <= EPSILON:
				frappe.throw(_("成品卷 {0} 已全部退货，不能重复处理").format(source.roll_no))
			return_weight = flt(row.return_weight or source.remaining_weight)
			return_yard_qty = flt(row.return_yard_qty or source.remaining_yard_qty)
			if return_weight <= 0 or return_yard_qty <= 0:
				frappe.throw(_("成品卷 {0} 的实退重量和码数必须大于 0").format(source.roll_no))
			if return_weight > flt(source.remaining_weight) + EPSILON or return_yard_qty > flt(source.remaining_yard_qty) + EPSILON:
				frappe.throw(_("成品卷 {0} 的实退数量超过尚可退数量").format(source.roll_no))
			is_full = abs(return_weight - flt(source.remaining_weight)) <= EPSILON and abs(return_yard_qty - flt(source.remaining_yard_qty)) <= EPSILON
			if not is_full and not (row.difference_reason or "").strip():
				frappe.throw(_("成品卷 {0} 为部分退货，请填写数量差异原因").format(source.roll_no))
			for fieldname in ("roll_no", "piece_no", "source_delivery", "source_packing_receipt",
				"packing_receipt_item", "finished_batch_no", "finished_grade"):
				row.set(fieldname, source.get(fieldname))
			row.original_quality_flag = source.quality_flag
			row.original_weight = source.weight
			row.original_yard_qty = source.yard_qty
			row.return_weight = return_weight
			row.return_yard_qty = return_yard_qty
			row.return_type = "整卷退货" if is_full else "部分退货"
			row.inspection_status = row.inspection_status or "待检"
			row.disposal_decision = row.disposal_decision or "未处理"

	def _set_totals(self):
		self.total_roll_count = len(self.items or [])
		self.total_weight = sum(flt(row.return_weight) for row in self.items or [])
		self.total_yard_qty = sum(flt(row.return_yard_qty) for row in self.items or [])

	def _set_delivery_summary(self):
		summary = get_return_flow_card_details(self.production_flow_card)
		for fieldname in ("delivered_roll_count", "delivered_weight", "delivered_yard_qty", "previous_return_weight", "returnable_weight", "returnable_yard_qty"):
			self.set(fieldname, summary.get(fieldname) or 0)

	def _validate_target_warehouse(self):
		warehouse = frappe.db.get_value("Warehouse", self.target_warehouse, ["company", "is_group", "disabled"], as_dict=True)
		if not warehouse or warehouse.is_group or warehouse.disabled:
			frappe.throw(_("未找到已启用的成品退货待检仓：{0}").format(self.target_warehouse))
		return warehouse

	def _create_stock_entry(self):
		if self.stock_entry:
			return
		warehouse = self._validate_target_warehouse()
		rates = [(flt(row.return_weight), _delivery_valuation_rate(row.source_delivery)) for row in self.items]
		total_weight = sum(weight for weight, _rate in rates)
		valuation_rate = sum(weight * rate for weight, rate in rates) / total_weight if total_weight else 0
		entry = frappe.get_doc({
			"doctype": "Stock Entry", "stock_entry_type": "Material Receipt", "purpose": "Material Receipt",
			"company": warehouse.company, "posting_date": self.return_date,
			"to_warehouse": self.target_warehouse, "custom_finished_product_return": self.name,
			"remarks": _("Finished product return: {0}; flow card: {1}; received for inspection").format(self.name, self.production_flow_card),
			"items": [{
				"item_code": self.finished_item_code, "qty": flt(self.total_weight),
				"basic_rate": valuation_rate, "uom": get_setting("weight_uom"),
				"t_warehouse": self.target_warehouse, "batch_no": self.finished_batch_no,
				"use_serial_batch_fields": 1, "allow_zero_valuation_rate": 1,
				"custom_roll_count": self.total_roll_count, "custom_yard_qty": self.total_yard_qty,
				"custom_yard_uom": get_setting("yard_uom"), "custom_production_flow_card": self.production_flow_card,
				"custom_finished_product_return": self.name,
			}],
		})
		entry.insert(ignore_permissions=True)
		entry.submit()
		self.db_set("stock_entry", entry.name, update_modified=False)

	def _record_progress(self, status):
		description = _("Returned {0} rolls, {1} Kg, {2} Y, received into {3}").format(
			self.total_roll_count, self.total_weight, self.total_yard_qty, self.target_warehouse,
		)
		filters = {"parent": self.production_flow_card, "source_doctype": self.doctype, "source_document": self.name}
		progress = frappe.db.get_value("Production Flow Card Progress", filters, "name")
		if progress:
			frappe.db.set_value("Production Flow Card Progress", progress, {"progress_status": status, "description": description}, update_modified=False)
		else:
			record_production_progress(
				self.production_flow_card, "成品退货", status, self.doctype, self.name,
				batch_no=self.finished_batch_no, quantity=self.total_weight, uom=get_setting("weight_uom"),
				roll_count=self.total_roll_count, yard_qty=self.total_yard_qty, description=description,
			)


def _delivery_valuation_rate(delivery):
	stock_entry = frappe.db.get_value("Finished Product Delivery", delivery, "stock_entry")
	if not stock_entry:
		return 0
	row = frappe.db.get_value("Stock Entry Detail", {"parent": stock_entry}, ["basic_rate", "valuation_rate"], as_dict=True)
	return flt(row.basic_rate or row.valuation_rate) if row else 0


def _returnable_delivery_item(name):
	rows = _returnable_roll_rows(source_delivery_item=name)
	return rows[0] if rows else None


def _returnable_roll_rows(flow_card=None, source_delivery_item=None):
	conditions = ["delivery.docstatus = 1", "delivery.delivery_status = '已出库'"]
	values = {}
	if flow_card:
		conditions.append("delivery.production_flow_card = %(flow_card)s")
		values["flow_card"] = flow_card
	if source_delivery_item:
		conditions.append("delivery_item.name = %(source_delivery_item)s")
		values["source_delivery_item"] = source_delivery_item
	return frappe.db.sql(
		f"""SELECT delivery_item.name, delivery_item.name AS source_delivery_item,
			delivery.name AS source_delivery, delivery.delivery_date, delivery.production_flow_card,
			delivery.customer, delivery.customer_name, delivery.stock_entry,
			delivery_item.packing_receipt_item, delivery_item.source_packing_receipt,
			delivery_item.roll_no, delivery_item.piece_no, delivery_item.finished_batch_no,
			delivery_item.weight, delivery_item.yard_qty, delivery_item.finished_grade,
			delivery_item.quality_flag, COALESCE(returned.return_weight, 0) AS returned_weight,
			COALESCE(returned.return_yard_qty, 0) AS returned_yard_qty,
			GREATEST(delivery_item.weight - COALESCE(returned.return_weight, 0), 0) AS remaining_weight,
			GREATEST(delivery_item.yard_qty - COALESCE(returned.return_yard_qty, 0), 0) AS remaining_yard_qty
		FROM `tabFinished Product Delivery Item` delivery_item
		INNER JOIN `tabFinished Product Delivery` delivery ON delivery.name = delivery_item.parent
		LEFT JOIN (
			SELECT return_item.source_delivery_item, SUM(return_item.return_weight) AS return_weight,
				SUM(return_item.return_yard_qty) AS return_yard_qty
			FROM `tabFinished Product Return Item` return_item
			INNER JOIN `tabFinished Product Return` return_doc ON return_doc.name = return_item.parent
			WHERE return_doc.docstatus = 1 AND return_doc.return_status = '已收货待检'
			GROUP BY return_item.source_delivery_item
		) returned ON returned.source_delivery_item = delivery_item.name
		WHERE {' AND '.join(conditions)}
		ORDER BY delivery.delivery_date, delivery.creation, delivery_item.idx""",
		values, as_dict=True,
	)


@frappe.whitelist()
def get_return_flow_card_details(flow_card):
	if not flow_card or not frappe.db.exists("Production Flow Card", {"name": flow_card, "docstatus": 1}):
		frappe.throw(_("请选择已提交的生产流转卡"))
	rows = _returnable_roll_rows(flow_card=flow_card)
	all_rows = frappe.db.sql(
		"""SELECT delivery_item.weight, delivery_item.yard_qty
		FROM `tabFinished Product Delivery Item` delivery_item
		INNER JOIN `tabFinished Product Delivery` delivery ON delivery.name = delivery_item.parent
		WHERE delivery.production_flow_card=%s AND delivery.docstatus=1 AND delivery.delivery_status='已出库'""",
		flow_card, as_dict=True,
	)
	if not all_rows:
		frappe.throw(_("该流转卡尚无已提交成品出库记录"))
	product = frappe.db.get_value(
		"Finished Product Delivery", {"production_flow_card": flow_card, "docstatus": 1, "delivery_status": "已出库"},
		["sales_order", "customer", "customer_name", "finished_item_code", "finished_batch_no",
		 "finished_product_name", "finished_specification", "color_no", "color"], as_dict=True,
	)
	delivered_weight = sum(flt(row.weight) for row in all_rows)
	returnable_weight = sum(flt(row.remaining_weight) for row in rows)
	return {
		**product, "target_warehouse": get_setting("finished_product_return_warehouse"),
		"delivered_roll_count": len(all_rows), "delivered_weight": delivered_weight,
		"delivered_yard_qty": sum(flt(row.yard_qty) for row in all_rows),
		"previous_return_weight": delivered_weight - returnable_weight,
		"returnable_weight": returnable_weight,
		"returnable_yard_qty": sum(flt(row.remaining_yard_qty) for row in rows),
	}


@frappe.whitelist()
def get_returnable_finished_rolls(doctype, txt, searchfield, start, page_len, filters, as_dict=False, **kwargs):
	filters = frappe.parse_json(filters) or {}
	rows = _returnable_roll_rows(flow_card=filters.get("production_flow_card"))
	excluded = set(frappe.parse_json(filters.get("excluded_names") or "[]") or [])
	rows = [row for row in rows if row.name not in excluded and flt(row.remaining_weight) > EPSILON and flt(row.remaining_yard_qty) > EPSILON]
	text = (txt or "").lower()
	rows = [row for row in rows if not text or text in (row.roll_no or "").lower() or text in (row.source_delivery or "").lower()]
	rows = rows[start:start + page_len]
	if as_dict:
		return [{"name": row.name, "匹号": row.piece_no, "成品卷号": row.roll_no,
			"尚可退重量(Kg)": row.remaining_weight, "尚可退码数(Y)": row.remaining_yard_qty,
			"来源成品出库单": row.source_delivery} for row in rows]
	return [[row.name, row.piece_no, row.roll_no, row.remaining_weight, row.remaining_yard_qty, row.source_delivery] for row in rows]


@frappe.whitelist()
def get_returnable_roll_details(names):
	names = frappe.parse_json(names) or []
	return [row for name in names if (row := _returnable_delivery_item(name))]


def refresh_roll_return_status(packing_receipt_item):
	if not packing_receipt_item:
		return
	packing = frappe.db.get_value("Finished Product Packing Receipt Item", packing_receipt_item, ["weight", "yard_qty"], as_dict=True)
	if not packing:
		return
	returned = frappe.db.sql(
		"""SELECT COALESCE(SUM(item.return_weight),0) AS weight, COALESCE(SUM(item.return_yard_qty),0) AS yard_qty
		FROM `tabFinished Product Return Item` item
		INNER JOIN `tabFinished Product Return` parent ON parent.name=item.parent
		WHERE item.packing_receipt_item=%s AND parent.docstatus=1 AND parent.return_status='已收货待检'""",
		packing_receipt_item, as_dict=True,
	)[0]
	if flt(returned.weight) <= EPSILON:
		status = "已出库"
	elif flt(returned.weight) + EPSILON < flt(packing.weight):
		status = "部分退货"
	else:
		status = "已退货待检"
	frappe.db.set_value("Finished Product Packing Receipt Item", packing_receipt_item, "warehouse_status", status, update_modified=False)


def refresh_return_summaries(flow_card):
	from dyeing_finishing.dyeing_finishing.doctype.finished_product_delivery.finished_product_delivery import refresh_delivery_progress
	returns = frappe.get_all(
		"Finished Product Return", {"production_flow_card": flow_card, "docstatus": 1, "return_status": "已收货待检"},
		["total_roll_count", "total_weight", "total_yard_qty"],
	)
	if returns:
		frappe.db.set_value("Production Flow Card", flow_card, "current_progress_status", "成品退货待处理", update_modified=False)
	else:
		refresh_delivery_progress(flow_card)
	deliveries = frappe.get_all("Finished Product Delivery", {"production_flow_card": flow_card, "docstatus": 1}, pluck="name")
	for delivery in deliveries:
		rows = frappe.db.sql(
			"""SELECT COUNT(DISTINCT item.source_delivery_item) AS roll_count,
				COALESCE(SUM(item.return_weight),0) AS weight, COALESCE(SUM(item.return_yard_qty),0) AS yard_qty
			FROM `tabFinished Product Return Item` item
			INNER JOIN `tabFinished Product Return` parent ON parent.name=item.parent
			WHERE item.source_delivery=%s AND parent.docstatus=1 AND parent.return_status='已收货待检'""",
			delivery, as_dict=True,
		)[0]
		frappe.db.set_value("Finished Product Delivery", delivery, {
			"returned_roll_count": rows.roll_count, "returned_weight": rows.weight, "returned_yard_qty": rows.yard_qty,
		}, update_modified=False)


def handle_stock_entry_cancel(doc, method=None):
	if not doc.get("custom_finished_product_return") or doc.flags.from_finished_product_return:
		return
	return_doc = frappe.get_doc("Finished Product Return", doc.custom_finished_product_return)
	if return_doc.docstatus != 1:
		return
	return_doc.db_set({"stock_entry": None, "return_status": "保存"}, update_modified=False)
	for row in return_doc.items:
		refresh_roll_return_status(row.packing_receipt_item)
	return_doc._record_progress("成品退货入库凭证已取消")
	refresh_return_summaries(return_doc.production_flow_card)
