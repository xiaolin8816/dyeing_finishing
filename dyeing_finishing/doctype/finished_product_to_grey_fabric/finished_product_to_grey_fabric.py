import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import getseries
from frappe.utils import flt, getdate, nowdate
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry

from dyeing_finishing.dyeing_finishing.doctype.finished_product_return_to_grey_fabric.finished_product_return_to_grey_fabric import _original_grey_fabric
from dyeing_finishing.dyeing_finishing.doctype.production_flow_card.production_flow_card import record_production_progress, remove_production_progress
from dyeing_finishing.dyeing_finishing.settings import get_setting


class FinishedProducttoGreyFabric(Document):
	def autoname(self):
		date = getdate(self.transfer_date or nowdate())
		prefix = f"ZC{date:%y%m%d}"
		self.name = f"{prefix}{getseries(prefix, 3)}"

	def before_insert(self):
		self.transfer_no = self.name
		self.transfer_status = "保存"
		if not self.return_batch_no:
			date = getdate(self.transfer_date or nowdate())
			prefix = f"F{date:%y%m%d}"
			self.return_batch_no = f"{prefix}{getseries(prefix, 3)}"

	def validate(self):
		self.transfer_no = self.name
		self.transfer_date = self.transfer_date or getdate(nowdate())
		self.target_warehouse = self.target_warehouse or get_setting("return_rework_warehouse")
		self._set_flow_details()
		self._validate_batch()
		self._validate_rows()
		self._set_totals()

	def on_submit(self):
		self._create_stock_entry()
		for row in self.items:
			frappe.db.set_value("Finished Product Packing Receipt Item", row.packing_receipt_item, "warehouse_status", "已转胚布仓", update_modified=False)
		self.db_set({"transfer_status": "已转胚布仓", "operator": frappe.session.user}, update_modified=False)
		self._record_progress("成品库存已转胚布仓")
		self._create_rework_flow_card()

	def before_cancel(self):
		if not self.rework_flow_card or not frappe.db.exists("Production Flow Card", self.rework_flow_card):
			return
		card = frappe.get_doc("Production Flow Card", self.rework_flow_card)
		if card.docstatus == 1:
			frappe.throw(_("请先取消关联的回修生产流转卡 {0}").format(card.name))
		frappe.delete_doc("Production Flow Card", card.name, ignore_permissions=True)
		self.db_set("rework_flow_card", None, update_modified=False)

	def on_cancel(self):
		if self.stock_entry:
			entry = frappe.get_doc("Stock Entry", self.stock_entry)
			self.db_set("stock_entry", None, update_modified=False)
			if entry.docstatus == 1:
				entry.update_stock_ledger = StockEntry.update_stock_ledger.__get__(entry, entry.__class__)
				entry.flags.from_finished_product_to_grey = True
				entry.cancel()
		for row in self.items:
			frappe.db.set_value("Finished Product Packing Receipt Item", row.packing_receipt_item, "warehouse_status", "已入库", update_modified=False)
		self.db_set("transfer_status", "已取消", update_modified=False)
		self._record_progress("成品库存转胚布仓已取消")

	def on_trash(self):
		remove_production_progress(self.doctype, self.name)

	def _set_flow_details(self):
		if not self.production_flow_card:
			frappe.throw(_("请选择原生产流转卡"))
		card = frappe.get_doc("Production Flow Card", self.production_flow_card)
		if card.docstatus != 1:
			frappe.throw(_("只能选择已提交的生产流转卡"))
		packing = frappe.db.get_value("Finished Product Packing Receipt", {"production_flow_card": card.name, "docstatus": 1, "packing_status": "已入库"},
			["sales_order", "customer", "customer_name", "finished_product_name", "color_no", "color", "finished_item_code", "finished_batch_no", "target_warehouse"], as_dict=True)
		if not packing:
			frappe.throw(_("该生产流转卡没有已入库成品"))
		for field in ("sales_order", "customer", "customer_name", "finished_product_name", "color_no", "color", "finished_item_code", "finished_batch_no"):
			self.set(field, packing.get(field))
		self.source_warehouse = packing.target_warehouse or get_setting("finished_product_warehouse")
		grey = _original_grey_fabric(card.name)
		self.grey_fabric_item, self.grey_fabric_name = grey.item_code, grey.grey_fabric_name

	def _validate_batch(self):
		if not self.return_batch_no:
			frappe.throw(_("保存后应自动生成返修胚布批次号"))
		if frappe.db.exists("Batch", self.return_batch_no):
			item = frappe.db.get_value("Batch", self.return_batch_no, "item")
			if item != self.grey_fabric_item:
				frappe.throw(_("批次号 {0} 已属于其他物料").format(self.return_batch_no))
		if not frappe.db.get_value("Item", self.grey_fabric_item, "has_batch_no"):
			frappe.throw(_("返修胚布物料必须启用批次管理"))

	def _validate_rows(self):
		if not self.items:
			frappe.throw(_("请至少选择一卷成品"))
		seen = set()
		identity = None
		for row in self.items:
			if not row.packing_receipt_item or row.packing_receipt_item in seen:
				frappe.throw(_("转胚布明细存在重复成品卷"))
			seen.add(row.packing_receipt_item)
			source = _available_packing_item(row.packing_receipt_item, self.name if not self.is_new() else None)
			if not source or source.production_flow_card != self.production_flow_card:
				frappe.throw(_("成品卷 {0} 已不可转仓或不属于当前流转卡").format(row.roll_no or row.packing_receipt_item))
			current_identity = (source.finished_item_code, source.finished_batch_no)
			if identity and current_identity != identity:
				frappe.throw(_("同一张转胚布仓单只能选择当前成品物料和批次相同的成品卷。"))
			identity = current_identity
			for field in ("piece_no", "weight", "yard_qty", "finished_grade", "quality_flag", "grey_fabric_batch", "source_packing_receipt", "source_warehouse", "finished_item_code", "finished_batch_no", "roll_no"):
				row.set(field, source.get(field))
		if identity:
			self.finished_item_code, self.finished_batch_no = identity

	def _set_totals(self):
		self.total_roll_count = len(self.items or [])
		self.total_weight = sum(flt(row.weight) for row in self.items or [])
		self.total_yard_qty = sum(flt(row.yard_qty) for row in self.items or [])

	def _ensure_batch(self):
		if frappe.db.exists("Batch", self.return_batch_no):
			return self.return_batch_no
		batch = frappe.get_doc({"doctype": "Batch", "batch_id": self.return_batch_no, "item": self.grey_fabric_item,
			"manufacturing_date": self.transfer_date, "description": _("\u6210\u54c1\u5e93\u5b58\u8f6c\u80da\u5e03\u4ed3\uff1a{0}").format(self.name)})
		batch.insert(ignore_permissions=True)
		return batch.name

	def _create_stock_entry(self):
		if self.stock_entry:
			return
		company = frappe.db.get_value("Warehouse", self.source_warehouse, "company")
		if not company or not frappe.db.exists("Warehouse", self.target_warehouse):
			frappe.throw(_("请检查来源成品仓库和目标胚布仓库"))
		batch = self._ensure_batch()
		entry = frappe.get_doc({"doctype":"Stock Entry", "stock_entry_type":"Repack", "purpose":"Repack", "company":company,
			"posting_date":self.transfer_date, "custom_finished_product_to_grey_fabric":self.name,
			"remarks":_("成品库存转胚布仓：{0}").format(self.name), "items":[
				{"item_code":self.finished_item_code,"qty":self.total_weight,"uom":get_setting("weight_uom"),"s_warehouse":self.source_warehouse,"batch_no":self.finished_batch_no,"use_serial_batch_fields":1,"custom_roll_count":self.total_roll_count,"custom_yard_qty":self.total_yard_qty,"custom_yard_uom":get_setting("yard_uom"),"custom_production_flow_card":self.production_flow_card,"custom_finished_product_to_grey_fabric":self.name},
				{"item_code":self.grey_fabric_item,"qty":self.total_weight,"uom":frappe.db.get_value("Item",self.grey_fabric_item,"stock_uom"),"t_warehouse":self.target_warehouse,"batch_no":batch,"use_serial_batch_fields":1,"allow_zero_valuation_rate":1,"custom_roll_count":self.total_roll_count,"custom_yard_qty":self.total_yard_qty,"custom_yard_uom":get_setting("yard_uom"),"custom_production_flow_card":self.production_flow_card,"custom_finished_product_to_grey_fabric":self.name}
			]})
		entry.insert(ignore_permissions=True)
		entry.submit()
		self.db_set("stock_entry", entry.name, update_modified=False)

	def _create_rework_flow_card(self):
		if self.rework_flow_card:
			return
		from dyeing_finishing.dyeing_finishing.doctype.production_flow_card.production_flow_card import create_rework_flow_card_from_internal_transfer
		card = create_rework_flow_card_from_internal_transfer(self.name)
		self.db_set("rework_flow_card", card, update_modified=False)

	def _record_progress(self, status):
		record_production_progress(self.production_flow_card, "成品库存转胚布", status, self.doctype, self.name,
			batch_no=self.return_batch_no, quantity=self.total_weight, uom=get_setting("weight_uom"), roll_count=self.total_roll_count,
			yard_qty=self.total_yard_qty, description=_("成品库存转为返修胚布批次 {0}").format(self.return_batch_no))


def _available_rows(flow_card=None, packing_item=None):
	conditions, values = ["parent.docstatus=1", "parent.packing_status='已入库'", "item.warehouse_status='已入库'"], {}
	if flow_card:
		conditions.append("parent.production_flow_card=%(flow_card)s"); values["flow_card"] = flow_card
	if packing_item:
		conditions.append("item.name=%(packing_item)s"); values["packing_item"] = packing_item
	return frappe.db.sql(f"""SELECT item.name, item.name AS packing_receipt_item, parent.name AS source_packing_receipt,
		parent.production_flow_card, parent.target_warehouse AS source_warehouse,
		COALESCE(NULLIF(item.current_finished_item_code, ''), parent.finished_item_code) AS finished_item_code,
		COALESCE(NULLIF(item.current_finished_batch_no, ''), parent.finished_batch_no) AS finished_batch_no,
		item.piece_no, item.roll_no, item.weight, item.yard_qty, item.finished_grade, item.quality_flag, item.grey_fabric_batch
	FROM `tabFinished Product Packing Receipt Item` item
	INNER JOIN `tabFinished Product Packing Receipt` parent ON parent.name=item.parent
	WHERE {' AND '.join(conditions)}
	AND NOT EXISTS (SELECT 1 FROM `tabFinished Product Delivery Item` delivery WHERE delivery.packing_receipt_item=item.name AND delivery.docstatus=1)
	AND NOT EXISTS (SELECT 1 FROM `tabFinished Product to Grey Fabric Item` moved_item INNER JOIN `tabFinished Product to Grey Fabric` moved ON moved.name=moved_item.parent WHERE moved_item.packing_receipt_item=item.name AND moved.docstatus=1)
	ORDER BY parent.packing_date,parent.creation,item.idx""", values, as_dict=True)


def _available_packing_item(name, current_doc=None):
	rows = _available_rows(packing_item=name)
	if rows:
		return rows[0]
	if current_doc:
		rows = frappe.db.sql("""SELECT item.name, item.name AS packing_receipt_item, parent.name AS source_packing_receipt,
			parent.production_flow_card, parent.target_warehouse AS source_warehouse,
			COALESCE(NULLIF(item.current_finished_item_code, ''), parent.finished_item_code) AS finished_item_code,
			COALESCE(NULLIF(item.current_finished_batch_no, ''), parent.finished_batch_no) AS finished_batch_no,
			item.piece_no,item.roll_no,item.weight,item.yard_qty,item.finished_grade,item.quality_flag,item.grey_fabric_batch
			FROM `tabFinished Product Packing Receipt Item` item INNER JOIN `tabFinished Product Packing Receipt` parent ON parent.name=item.parent
			WHERE item.name=%s AND item.warehouse_status='已入库'""", name, as_dict=True)
		return rows[0] if rows else None
	return None


@frappe.whitelist()
def get_flow_details(flow_card):
	rows = _available_rows(flow_card=flow_card)
	if not rows:
		frappe.throw(_("该生产流转卡没有可转胚布仓的已入库成品卷"))
	doc = frappe.new_doc("Finished Product to Grey Fabric")
	doc.production_flow_card = flow_card
	doc._set_flow_details()
	doc.target_warehouse = get_setting("return_rework_warehouse")
	return {field: doc.get(field) for field in ("sales_order","customer","customer_name","finished_product_name","color_no","color","finished_item_code","finished_batch_no","source_warehouse","target_warehouse","grey_fabric_item","grey_fabric_name")}


@frappe.whitelist()
def get_available_items(doctype, txt, searchfield, start, page_len, filters, as_dict=False, **kwargs):
	filters = frappe.parse_json(filters) or {}; excluded = set(frappe.parse_json(filters.get("excluded_names") or "[]") or [])
	rows = [row for row in _available_rows(filters.get("production_flow_card")) if row.name not in excluded]
	txt = (txt or "").lower(); rows = [row for row in rows if not txt or txt in (row.roll_no or "").lower() or txt in (row.source_packing_receipt or "").lower()]
	rows = rows[int(start):int(start)+int(page_len)]
	if as_dict:
		return [{"name":r.name,"匹号":r.piece_no,"重量(Kg)":r.weight,"码数(Y)":r.yard_qty,"原包装入库单":r.source_packing_receipt,"成品卷号":r.roll_no} for r in rows]
	return [[r.name,r.piece_no,r.weight,r.yard_qty,r.source_packing_receipt,r.roll_no] for r in rows]


@frappe.whitelist()
def get_item_details(names):
	return [row for name in (frappe.parse_json(names) or []) if (row := _available_packing_item(name))]


def handle_stock_entry_cancel(doc, method=None):
	if not doc.get("custom_finished_product_to_grey_fabric") or doc.flags.from_finished_product_to_grey:
		return
	transfer = frappe.get_doc("Finished Product to Grey Fabric", doc.custom_finished_product_to_grey_fabric)
	if transfer.docstatus == 1:
		frappe.throw(_("请通过成品库存转胚布仓单 {0} 执行取消").format(transfer.name))
