import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import getseries
from frappe.utils import cint, flt, getdate, now, nowdate
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry

from dyeing_finishing.dyeing_finishing.settings import get_setting


class GreyFabricCustomerTransfer(Document):
	def insert(self, *args, **kwargs):
		self._reset_amended_inventory_links()
		return super().insert(*args, **kwargs)

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._reset_amended_inventory_links()

	def _reset_amended_inventory_links(self):
		if not self.get("amended_from") or cint(self.docstatus) != 0:
			return
		self.stock_entry = None
		self.confirmed_at = None
		for row in self.items or []:
			row.target_batch_no = None

	def autoname(self):
		date = getdate(self.transfer_date or nowdate())
		prefix = f"GH{date:%y%m%d}"
		self.name = f"{prefix}{getseries(prefix, 3)}"

	def before_insert(self):
		self.transfer_no = self.name
		self.transfer_status = "保存"
		self.operator = frappe.session.user
		self.stock_entry = None
		self.confirmed_at = None
		for row in self.items:
			row.target_batch_no = None

	def validate(self):
		self.transfer_no = self.name
		self.transfer_date = self.transfer_date or getdate(nowdate())
		self._set_customer_names()
		if self.source_customer == self.target_customer:
			frappe.throw(_("新客户不能与原客户相同。"))
		self._validate_items()
		self._set_totals()

	def on_submit(self):
		self._create_stock_entry()
		self.db_set({"transfer_status":"已过户", "operator":frappe.session.user, "confirmed_at":now()}, update_modified=False)

	def before_cancel(self):
		for row in self.items:
			if frappe.db.exists("Grey Fabric Issue Item", {"batch_no":row.target_batch_no, "docstatus":1}):
				frappe.throw(_("新批次 {0} 已被胚布出库引用，不能取消过户。").format(row.target_batch_no))
			if frappe.db.exists("Grey Fabric Customer Transfer Item", {"source_batch_no":row.target_batch_no, "docstatus":1}):
				frappe.throw(_("新批次 {0} 已再次过户，请先取消后续过户单。").format(row.target_batch_no))
		if self.stock_entry:
			stock_entry = self.stock_entry
			entry = frappe.get_doc("Stock Entry", stock_entry)
			self.db_set("stock_entry", None, update_modified=False)
			if entry.docstatus == 1:
				entry.update_stock_ledger = StockEntry.update_stock_ledger.__get__(entry, entry.__class__)
				entry.flags.from_grey_fabric_customer_transfer = True
				entry.cancel()
			self.db_set("stock_entry", stock_entry, update_modified=False)
		self.ignore_linked_doctypes = ("Stock Entry",)

	def on_cancel(self):
		self.db_set("transfer_status", "已取消", update_modified=False)

	def _set_customer_names(self):
		self.source_customer_name = frappe.db.get_value("Customer", self.source_customer, "customer_name") or self.source_customer
		self.target_customer_name = frappe.db.get_value("Customer", self.target_customer, "customer_name") or self.target_customer

	def _validate_items(self):
		if not self.items:
			frappe.throw(_("请至少选择一个胚布批次。"))
		seen, warehouse = set(), None
		for index, row in enumerate(self.items, 1):
			if not row.source_batch_no or row.source_batch_no in seen:
				frappe.throw(_("胚布过户明细存在重复批次。"))
			seen.add(row.source_batch_no)
			source = _available_batch(row.source_batch_no, self.source_customer, row.source_warehouse)
			if not source:
				frappe.throw(_("批次 {0} 已无可过户库存或不属于原客户。").format(row.source_batch_no))
			if warehouse and warehouse != source.source_warehouse:
				frappe.throw(_("同一张胚布过户单只能选择同一仓库或货位的库存。"))
			warehouse = source.source_warehouse
			for field in ("item_code","item_name","color","source_warehouse","location","stock_roll_count","stock_qty"):
				row.set(field, source.get(field))
			if flt(row.transfer_qty) <= 0 or flt(row.transfer_qty) > flt(source.stock_qty) + 0.000001:
				frappe.throw(_("批次 {0} 的过户重量必须大于0且不能超过库存重量。").format(row.source_batch_no))
			if cint(row.transfer_roll_count) <= 0 or flt(row.transfer_roll_count) > flt(source.stock_roll_count) + 0.000001:
				frappe.throw(_("批次 {0} 的过户匹数必须大于0且不能超过库存匹数。").format(row.source_batch_no))
			row.remaining_qty = flt(source.stock_qty) - flt(row.transfer_qty)
			row.remaining_roll_count = flt(source.stock_roll_count) - flt(row.transfer_roll_count)
			if not row.target_batch_no or row.target_batch_no.startswith("GHP"):
				row.target_batch_no = self._next_transfer_batch_no()
		self.source_warehouse = warehouse

	def _next_transfer_batch_no(self):
		date = getdate(self.transfer_date or nowdate())
		prefix = f"G{date:%y%m%d}"
		while True:
			batch_no = f"{prefix}{getseries(prefix, 3)}"
			if not frappe.db.exists("Batch", batch_no):
				return batch_no

	def _set_totals(self):
		self.total_roll_count = sum(cint(row.transfer_roll_count) for row in self.items)
		self.total_weight = sum(flt(row.transfer_qty) for row in self.items)

	def _ensure_batches(self):
		for row in self.items:
			if frappe.db.exists("Batch", row.target_batch_no):
				if frappe.db.get_value("Batch", row.target_batch_no, "item") != row.item_code:
					frappe.throw(_("新批次 {0} 已属于其他物料。").format(row.target_batch_no))
				continue
			frappe.get_doc({"doctype":"Batch", "batch_id":row.target_batch_no, "item":row.item_code,
				"manufacturing_date":self.transfer_date, "description":_("胚布过户单：{0}；{1} → {2}").format(self.name, self.source_customer_name, self.target_customer_name)}).insert(ignore_permissions=True)

	def _create_stock_entry(self):
		if self.stock_entry:
			return
		self._ensure_batches()
		company = frappe.db.get_value("Warehouse", self.source_warehouse, "company")
		if not company:
			frappe.throw(_("过户仓库未设置公司。"))
		items = []
		for row in self.items:
			common = {"item_code":row.item_code, "qty":flt(row.transfer_qty), "uom":frappe.db.get_value("Item", row.item_code, "stock_uom"),
				"use_serial_batch_fields":1, "custom_roll_count":cint(row.transfer_roll_count), "custom_grey_fabric_customer_transfer":self.name}
			items.extend((
				{**common, "s_warehouse":row.source_warehouse, "batch_no":row.source_batch_no},
				{**common, "t_warehouse":row.source_warehouse, "batch_no":row.target_batch_no, "allow_zero_valuation_rate":1},
			))
		entry = frappe.get_doc({"doctype":"Stock Entry", "stock_entry_type":"Repack", "purpose":"Repack", "company":company,
			"posting_date":self.transfer_date, "custom_grey_fabric_customer_transfer":self.name,
			"remarks":_("胚布过户单：{0}；{1} → {2}").format(self.name, self.source_customer_name, self.target_customer_name), "items":items})
		entry.insert(ignore_permissions=True)
		entry.submit()
		self.db_set("stock_entry", entry.name, update_modified=False)


def _ownership_sql():
	return """SELECT batch_no, MAX(customer) AS customer, MAX(customer_name) AS customer_name, MAX(color) AS color
	FROM (
		SELECT ri.batch_no, r.customer, COALESCE(NULLIF(r.customer_name,''), c.customer_name, r.customer) customer_name, ri.color
		FROM `tabCustomer Grey Fabric Receipt Item` ri INNER JOIN `tabCustomer Grey Fabric Receipt` r ON r.name=ri.parent AND r.docstatus=1 LEFT JOIN `tabCustomer` c ON c.name=r.customer
		UNION ALL
		SELECT ti.target_batch_no, t.target_customer, COALESCE(NULLIF(t.target_customer_name,''), c.customer_name, t.target_customer), ti.color
		FROM `tabGrey Fabric Customer Transfer Item` ti INNER JOIN `tabGrey Fabric Customer Transfer` t ON t.name=ti.parent AND t.docstatus=1 LEFT JOIN `tabCustomer` c ON c.name=t.target_customer
		UNION ALL
		SELECT t.return_batch_no, t.customer, COALESCE(NULLIF(t.customer_name,''), c.customer_name, t.customer), card.color
		FROM `tabFinished Product to Grey Fabric` t LEFT JOIN `tabCustomer` c ON c.name=t.customer LEFT JOIN `tabProduction Flow Card` card ON card.name=t.production_flow_card WHERE t.docstatus=1
		UNION ALL
		SELECT t.return_batch_no, t.customer, COALESCE(NULLIF(t.customer_name,''), c.customer_name, t.customer), card.color
		FROM `tabFinished Product Return to Grey Fabric` t LEFT JOIN `tabCustomer` c ON c.name=t.customer LEFT JOIN `tabProduction Flow Card` card ON card.name=t.production_flow_card WHERE t.docstatus=1
	) owners GROUP BY batch_no"""


def _available_rows(customer=None):
	values, condition = {}, ""
	if customer:
		condition = "AND owner.customer=%(customer)s"; values["customer"] = customer
	return frappe.db.sql(f"""SELECT stock.batch_no, stock.item_code, item.item_name, owner.color,
		stock.warehouse AS source_warehouse, warehouse.parent_warehouse AS location,
		stock.stock_qty, GREATEST(COALESCE(receipt_rolls.roll_count,0)+COALESCE(rolls.roll_count,0),0) AS stock_roll_count,
		owner.customer, owner.customer_name
	FROM (SELECT sle.item_code, COALESCE(NULLIF(sle.batch_no,''), sbe.batch_no) batch_no, sle.warehouse, SUM(sle.actual_qty) stock_qty
		FROM `tabStock Ledger Entry` sle LEFT JOIN `tabSerial and Batch Entry` sbe ON sbe.parent=sle.serial_and_batch_bundle
		WHERE sle.is_cancelled=0 GROUP BY sle.item_code,COALESCE(NULLIF(sle.batch_no,''),sbe.batch_no),sle.warehouse HAVING stock_qty>0.000001) stock
	INNER JOIN `tabItem` item ON item.name=stock.item_code
	INNER JOIN ({_ownership_sql()}) owner ON owner.batch_no=stock.batch_no
	LEFT JOIN `tabWarehouse` warehouse ON warehouse.name=stock.warehouse
	LEFT JOIN (SELECT ri.batch_no,SUM(ri.roll_count) roll_count FROM `tabCustomer Grey Fabric Receipt Item` ri
		INNER JOIN `tabCustomer Grey Fabric Receipt` r ON r.name=ri.parent AND r.docstatus=1 GROUP BY ri.batch_no) receipt_rolls
		ON receipt_rolls.batch_no=stock.batch_no
	LEFT JOIN (SELECT item_code,batch_no,warehouse,SUM(delta) roll_count FROM (
		SELECT d.item_code,d.batch_no,d.t_warehouse warehouse,COALESCE(d.custom_roll_count,0) delta FROM `tabStock Entry Detail` d INNER JOIN `tabStock Entry` e ON e.name=d.parent AND e.docstatus=1 WHERE COALESCE(d.t_warehouse,'')!=''
		UNION ALL SELECT d.item_code,d.batch_no,d.s_warehouse,-COALESCE(d.custom_roll_count,0) FROM `tabStock Entry Detail` d INNER JOIN `tabStock Entry` e ON e.name=d.parent AND e.docstatus=1 WHERE COALESCE(d.s_warehouse,'')!='') movement GROUP BY item_code,batch_no,warehouse) rolls
		ON rolls.item_code=stock.item_code AND rolls.batch_no=stock.batch_no AND rolls.warehouse=stock.warehouse
	WHERE stock.warehouse != %(transit_warehouse)s AND item.item_group IN (SELECT name FROM `tabItem Group` WHERE lft >= (SELECT lft FROM `tabItem Group` WHERE name=%(grey_group)s) AND rgt <= (SELECT rgt FROM `tabItem Group` WHERE name=%(grey_group)s)) {condition}
	ORDER BY stock.batch_no,stock.warehouse""", {**values, "grey_group":get_setting("grey_fabric_item_group"), "transit_warehouse":get_setting("production_transit_warehouse")}, as_dict=True)


def _available_batch(batch_no, customer, warehouse=None):
	return next((row for row in _available_rows(customer) if row.batch_no == batch_no and (not warehouse or row.source_warehouse == warehouse)), None)


@frappe.whitelist()
def get_available_batches(doctype, txt, searchfield, start, page_len, filters, as_dict=False, **kwargs):
	filters = frappe.parse_json(filters) or {}; excluded=set(frappe.parse_json(filters.get("excluded_names") or "[]") or [])
	rows=[r for r in _available_rows(filters.get("customer")) if r.batch_no not in excluded]
	txt=(txt or "").lower(); rows=[r for r in rows if not txt or txt in r.batch_no.lower() or txt in (r.item_name or "").lower()]
	rows=rows[cint(start):cint(start)+cint(page_len)]
	if as_dict:
		return [{"name":r.batch_no,"胚布名称":r.item_name,"库存匹数":r.stock_roll_count,"库存重量(Kg)":r.stock_qty,"仓库/货位":r.source_warehouse} for r in rows]
	return [[r.batch_no,r.item_name,r.stock_roll_count,r.stock_qty,r.source_warehouse] for r in rows]


@frappe.whitelist()
def get_batch_details(names, customer):
	names=frappe.parse_json(names) or []
	return [row for row in _available_rows(customer) if row.batch_no in names]


def handle_stock_entry_cancel(doc, method=None):
	if not doc.get("custom_grey_fabric_customer_transfer") or doc.flags.from_grey_fabric_customer_transfer:
		return
	if frappe.form_dict.get("cmd") == "frappe.desk.form.linked_with.cancel_all_linked_docs":
		doc.update_stock_ledger = StockEntry.update_stock_ledger.__get__(doc, doc.__class__)
		doc.flags.from_grey_fabric_customer_transfer = True
		doc.flags.ignore_links = True
		return
	transfer=frappe.get_doc("Grey Fabric Customer Transfer",doc.custom_grey_fabric_customer_transfer)
	if transfer.docstatus==1:
		frappe.throw(_("请通过胚布过户单 {0} 执行取消。").format(transfer.name))
