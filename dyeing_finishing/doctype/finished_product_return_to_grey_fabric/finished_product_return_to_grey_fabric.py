import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import getseries
from frappe.utils import flt, getdate, nowdate
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry

from dyeing_finishing.dyeing_finishing.doctype.production_flow_card.production_flow_card import record_production_progress, remove_production_progress
from dyeing_finishing.dyeing_finishing.settings import get_setting


EPSILON = 0.000001


class FinishedProductReturntoGreyFabric(Document):
	def autoname(self):
		date = getdate(self.transfer_date or nowdate())
		prefix = f"ZPB{date:%y%m%d}"
		self.name = f"{prefix}{getseries(prefix, 3)}"

	def before_insert(self):
		self.transfer_no = self.name
		self.transfer_status = "保存"

	def validate(self):
		self.transfer_no = self.name
		self.transfer_date = self.transfer_date or getdate(nowdate())
		self.source_warehouse = get_setting("finished_product_return_warehouse")
		self.target_warehouse = get_setting("return_rework_warehouse")
		self._set_flow_details()
		self._validate_item_and_batch()
		self._validate_rows()
		self._set_totals()

	def on_submit(self):
		self._create_stock_entry()
		self.db_set({"transfer_status": "已转胚布", "operator": frappe.session.user}, update_modified=False)
		for row in self.items:
			_refresh_return_item_disposal(row.return_item)
		self._record_progress("退货已转胚布")

	def on_cancel(self):
		if self.stock_entry:
			entry = frappe.get_doc("Stock Entry", self.stock_entry)
			self.db_set("stock_entry", None, update_modified=False)
			if entry.docstatus == 1:
				entry.update_stock_ledger = StockEntry.update_stock_ledger.__get__(entry, entry.__class__)
				entry.flags.from_return_to_grey = True
				entry.cancel()
		self.db_set("transfer_status", "已取消", update_modified=False)
		for row in self.items:
			_refresh_return_item_disposal(row.return_item)
		self._record_progress("退货转胚布已取消")

	def on_trash(self):
		remove_production_progress(self.doctype, self.name)

	def _set_flow_details(self):
		if not self.production_flow_card:
			frappe.throw(_("请选择生产流转卡"))
		row = frappe.db.get_value("Finished Product Return", {"production_flow_card": self.production_flow_card, "docstatus": 1, "return_status": "已收货待检"}, ["sales_order", "customer", "customer_name"], as_dict=True)
		if not row:
			frappe.throw(_("该生产流转卡没有已收货待检的成品退货"))
		self.sales_order, self.customer, self.customer_name = row.sales_order, row.customer, row.customer_name
		grey = _original_grey_fabric(self.production_flow_card)
		self.grey_fabric_item, self.grey_fabric_name = grey.item_code, grey.grey_fabric_name

	def _validate_item_and_batch(self):
		if not self.grey_fabric_item:
			frappe.throw(_("请选择返修胚布物料"))
		if not self.return_batch_no or not self.return_batch_no.strip():
			frappe.throw(_("请填写返修胚布批次号"))
		self.return_batch_no = self.return_batch_no.strip()
		if frappe.db.exists("Batch", self.return_batch_no):
			batch = frappe.db.get_value("Batch", self.return_batch_no, "item")
			if batch != self.grey_fabric_item:
				frappe.throw(_("批次号 {0} 已属于其他物料").format(self.return_batch_no))
			if self.is_new():
				frappe.throw(_("返修胚布批次号 {0} 已存在，请填写新的批次号").format(self.return_batch_no))
		if not frappe.db.get_value("Item", self.grey_fabric_item, "has_batch_no"):
			frappe.throw(_("返修胚布物料必须启用批次管理"))

	def _validate_rows(self):
		if not self.items:
			frappe.throw(_("请至少选择一卷退货成品"))
		seen = set()
		for row in self.items:
			if not row.return_item or row.return_item in seen:
				frappe.throw(_("转胚布明细存在重复退货卷"))
			seen.add(row.return_item)
			source = _available_return_item(row.return_item, self.name if not self.is_new() else None)
			if not source or source.production_flow_card != self.production_flow_card:
				frappe.throw(_("成品卷 {0} 已不可转换或不属于当前流转卡").format(row.roll_no or row.return_item))
			weight, yards = flt(row.transfer_weight), flt(row.transfer_yard_qty)
			if weight <= 0 or yards <= 0 or weight > flt(source.available_weight) + EPSILON or yards > flt(source.available_yard_qty) + EPSILON:
				frappe.throw(_("成品卷 {0} 的转换数量超过可转数量").format(source.roll_no))
			for field in ("piece_no", "roll_no", "return_document", "source_delivery"):
				row.set(field, source.get(field))
			row.available_weight, row.available_yard_qty = source.available_weight, source.available_yard_qty

	def _set_totals(self):
		self.total_roll_count = len(self.items or [])
		self.total_weight = sum(flt(row.transfer_weight) for row in self.items or [])
		self.total_yard_qty = sum(flt(row.transfer_yard_qty) for row in self.items or [])

	def _ensure_batch(self):
		if frappe.db.exists("Batch", self.return_batch_no):
			return self.return_batch_no
		batch = frappe.get_doc({"doctype": "Batch", "batch_id": self.return_batch_no, "item": self.grey_fabric_item, "manufacturing_date": self.transfer_date, "description": _("成品退货转胚布仓：{0}").format(self.name)})
		batch.insert(ignore_permissions=True)
		return batch.name

	def _create_stock_entry(self):
		if self.stock_entry:
			return
		company = frappe.db.get_value("Warehouse", self.target_warehouse, "company")
		if not company or not frappe.db.exists("Warehouse", self.source_warehouse):
			frappe.throw(_("请检查成品退货待检仓和返修待处理仓设置"))
		first = frappe.db.get_value("Finished Product Return", self.items[0].return_document, ["finished_item_code", "finished_batch_no"], as_dict=True)
		batch = self._ensure_batch()
		entry = frappe.get_doc({"doctype":"Stock Entry", "stock_entry_type":"Repack", "purpose":"Repack", "company":company, "posting_date":self.transfer_date, "custom_finished_product_return_to_grey_fabric":self.name, "remarks":_("成品退货转胚布仓：{0}").format(self.name), "items":[
			{"item_code":first.finished_item_code,"qty":self.total_weight,"uom":get_setting("weight_uom"),"s_warehouse":self.source_warehouse,"batch_no":first.finished_batch_no,"use_serial_batch_fields":1,"custom_roll_count":self.total_roll_count,"custom_yard_qty":self.total_yard_qty,"custom_yard_uom":get_setting("yard_uom"),"custom_production_flow_card":self.production_flow_card,"custom_finished_product_return_to_grey_fabric":self.name},
			{"item_code":self.grey_fabric_item,"qty":self.total_weight,"uom":frappe.db.get_value("Item",self.grey_fabric_item,"stock_uom"),"t_warehouse":self.target_warehouse,"batch_no":batch,"use_serial_batch_fields":1,"allow_zero_valuation_rate":1,"custom_roll_count":self.total_roll_count,"custom_yard_qty":self.total_yard_qty,"custom_yard_uom":get_setting("yard_uom"),"custom_production_flow_card":self.production_flow_card,"custom_finished_product_return_to_grey_fabric":self.name}
		]})
		entry.insert(ignore_permissions=True)
		entry.submit()
		self.db_set("stock_entry", entry.name, update_modified=False)

	def _record_progress(self, status):
		record_production_progress(self.production_flow_card, "成品退货转胚布", status, self.doctype, self.name, batch_no=self.return_batch_no, quantity=self.total_weight, uom=get_setting("weight_uom"), roll_count=self.total_roll_count, yard_qty=self.total_yard_qty, description=_("退货成品转为返修胚布批次 {0}").format(self.return_batch_no))


def _available_rows(flow_card=None, return_item=None, current_doc=None):
	conditions, values = ["parent.docstatus=1", "parent.return_status='已收货待检'"], {}
	if flow_card: conditions.append("parent.production_flow_card=%(flow_card)s"); values["flow_card"] = flow_card
	if return_item: conditions.append("item.name=%(return_item)s"); values["return_item"] = return_item
	if current_doc: values["current_doc"] = current_doc
	return frappe.db.sql(f"""SELECT item.name, item.name AS return_item, parent.name AS return_document, parent.production_flow_card,
		item.piece_no, item.roll_no, item.source_delivery,
		GREATEST(item.return_weight-COALESCE(moved.weight,0),0) AS available_weight,
		GREATEST(item.return_yard_qty-COALESCE(moved.yards,0),0) AS available_yard_qty
	FROM `tabFinished Product Return Item` item INNER JOIN `tabFinished Product Return` parent ON parent.name=item.parent
	LEFT JOIN (SELECT child.return_item,SUM(child.transfer_weight) weight,SUM(child.transfer_yard_qty) yards FROM `tabFinished Product Return to Grey Fabric Item` child INNER JOIN `tabFinished Product Return to Grey Fabric` doc ON doc.name=child.parent WHERE doc.docstatus=1 GROUP BY child.return_item) moved ON moved.return_item=item.name
	WHERE {' AND '.join(conditions)} ORDER BY parent.return_date,item.idx""", values, as_dict=True)


def _available_return_item(name, current_doc=None):
	rows = _available_rows(return_item=name, current_doc=current_doc)
	return rows[0] if rows else None


def _original_grey_fabric(flow_card):
	rows = frappe.db.sql("""SELECT item.item_code, MAX(COALESCE(NULLIF(item.grey_fabric_name,''), master.fabric_name, product.item_name)) AS grey_fabric_name
		FROM `tabGrey Fabric Issue Item` item
		INNER JOIN `tabGrey Fabric Issue` issue ON issue.name=item.parent AND issue.docstatus=1
		LEFT JOIN `tabGrey Fabric Master` master ON master.item_code=item.item_code
		LEFT JOIN `tabItem` product ON product.name=item.item_code
		WHERE issue.flow_card=%s GROUP BY item.item_code ORDER BY item.item_code""", flow_card, as_dict=True)
	if not rows:
		frappe.throw(_("生产流转卡 {0} 没有已提交的胚布出库记录，无法确定返修胚布物料").format(flow_card))
	if len(rows) > 1:
		frappe.throw(_("生产流转卡 {0} 使用了多个胚布物料，不能自动合并转入一个返修批次").format(flow_card))
	return rows[0]


def _refresh_return_item_disposal(return_item):
	active = frappe.db.sql("""SELECT 1 FROM `tabFinished Product Return to Grey Fabric Item` child
		INNER JOIN `tabFinished Product Return to Grey Fabric` parent ON parent.name=child.parent
		WHERE child.return_item=%s AND parent.docstatus=1 LIMIT 1""", return_item)
	frappe.db.set_value("Finished Product Return Item", return_item, {
		"inspection_status": "已检验" if active else "待检",
		"disposal_decision": "返修" if active else "未处理",
	}, update_modified=False)


@frappe.whitelist()
def get_flow_details(flow_card):
	row = frappe.db.get_value("Finished Product Return", {"production_flow_card":flow_card,"docstatus":1,"return_status":"已收货待检"}, ["sales_order","customer","customer_name"], as_dict=True)
	if not row: frappe.throw(_("该生产流转卡没有已收货待检的成品退货"))
	grey = _original_grey_fabric(flow_card)
	return {**row, **grey, "grey_fabric_item":grey.item_code, "source_warehouse":get_setting("finished_product_return_warehouse"), "target_warehouse":get_setting("return_rework_warehouse")}


@frappe.whitelist()
def get_available_return_items(doctype, txt, searchfield, start, page_len, filters, as_dict=False, **kwargs):
	filters = frappe.parse_json(filters) or {}; excluded = set(frappe.parse_json(filters.get("excluded_names") or "[]") or [])
	rows = [r for r in _available_rows(flow_card=filters.get("production_flow_card")) if r.name not in excluded and flt(r.available_weight)>EPSILON and flt(r.available_yard_qty)>EPSILON and (not txt or txt.lower() in (r.roll_no or '').lower() or txt.lower() in (r.return_document or '').lower())]
	rows = rows[int(start):int(start)+int(page_len)]
	if as_dict: return [{"name":r.name,"匹号":r.piece_no,"可转重量(Kg)":r.available_weight,"可转码数(Y)":r.available_yard_qty,"来源退货处理单":r.return_document,"成品卷号":r.roll_no} for r in rows]
	return [[r.name,r.piece_no,r.available_weight,r.available_yard_qty,r.return_document,r.roll_no] for r in rows]


@frappe.whitelist()
def get_return_item_details(names):
	return [row for name in (frappe.parse_json(names) or []) if (row := _available_return_item(name))]


def handle_stock_entry_cancel(doc, method=None):
	if not doc.get("custom_finished_product_return_to_grey_fabric") or doc.flags.from_return_to_grey: return
	transfer = frappe.get_doc("Finished Product Return to Grey Fabric", doc.custom_finished_product_return_to_grey_fabric)
	if transfer.docstatus == 1:
		transfer.db_set({"stock_entry":None,"transfer_status":"保存"}, update_modified=False)
		transfer._record_progress("退货转胚布凭证已取消")
