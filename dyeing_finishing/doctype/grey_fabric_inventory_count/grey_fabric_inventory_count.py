import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import getseries
from frappe.utils import cint, flt, get_time, getdate, now, nowdate, nowtime

from dyeing_finishing.dyeing_finishing.doctype.grey_fabric_customer_transfer.grey_fabric_customer_transfer import _available_rows
from dyeing_finishing.dyeing_finishing.settings import get_setting


TOLERANCE = 0.000001
REVIEW_ROLES = {"Stock Manager", "System Manager"}


class GreyFabricInventoryCount(Document):
	def autoname(self):
		date = getdate(self.count_date or nowdate())
		prefix = f"PD{date:%y%m%d}"
		self.name = f"{prefix}{getseries(prefix, 3)}"

	def before_insert(self):
		self.status = "草稿"
		self.counted_by = self.counted_by or frappe.session.user
		self._normalize_posting_time()

	def validate(self):
		self.count_date = self.count_date or getdate(nowdate())
		self._normalize_posting_time()
		self._validate_scope()
		self._validate_items()
		self._set_totals()

	def before_submit(self):
		self._assert_snapshot_is_current()

	def on_submit(self):
		self.db_set("status", "待审核", update_modified=False)

	def _normalize_posting_time(self):
		value = str(self.posting_time or "")
		if not value or "nan" in value.lower():
			value = nowtime()
		try:
			self.posting_time = get_time(value)
		except (TypeError, ValueError):
			self.posting_time = get_time(nowtime())

	def before_cancel(self):
		stock_reconciliation = self.stock_reconciliation
		links = {
			"receipt_stock_entry": self.receipt_stock_entry,
			"issue_stock_entry": self.issue_stock_entry,
		}
		if stock_reconciliation:
			self.db_set("stock_reconciliation", None, update_modified=False)
			reconciliation = frappe.get_doc("Stock Reconciliation", stock_reconciliation)
			if reconciliation.docstatus == 1:
				reconciliation.cancel()
			self.db_set("stock_reconciliation", stock_reconciliation, update_modified=False)
		self.db_set({fieldname: None for fieldname in links}, update_modified=False)
		for stock_entry in links.values():
			if not stock_entry:
				continue
			entry = frappe.get_doc("Stock Entry", stock_entry)
			if entry.docstatus == 1:
				entry.cancel()
		self.db_set(links, update_modified=False)
		self.ignore_linked_doctypes = ("Stock Entry", "Stock Reconciliation")

	def on_cancel(self):
		self.db_set("status", "已取消", update_modified=False)

	def _validate_scope(self):
		warehouse = frappe.db.get_value("Warehouse", self.warehouse, ["is_group", "disabled"], as_dict=True)
		if not warehouse:
			frappe.throw(_("盘点仓库/货位不存在。"))
		if warehouse.is_group:
			frappe.throw(_("请选择可存放库存的末级仓库或货位，不能选择仓库组。"))
		if warehouse.disabled:
			frappe.throw(_("盘点仓库/货位已停用。"))
		if self.warehouse not in _inventory_count_warehouse_names():
			frappe.throw(_("请选择胚布仓库、胚布货位或返修待处理仓，其他仓库不能用于胚布盘点。"))

		duplicate = _find_overlapping_inventory_count(
			self.name, self.warehouse, self.customer
		)
		if duplicate:
			frappe.throw(_("相同盘点范围已有草稿或待审核的胚布盘点表 {0}，请先处理该单据。").format(duplicate))

	def _validate_items(self):
		if not self.items:
			frappe.throw(_("请先读取账面库存，至少保留一条盘点明细。"))
		seen = set()
		for row in self.items:
			key = (row.batch_no, row.stock_warehouse)
			if not row.batch_no or key in seen:
				frappe.throw(_("第 {0} 行批次为空或重复。").format(row.idx))
			seen.add(key)
			if not _warehouse_in_scope(row.stock_warehouse, self.warehouse):
				frappe.throw(_("第 {0} 行不属于本次盘点仓库/货位。").format(row.idx))
			if self.customer and row.customer != self.customer:
				frappe.throw(_("第 {0} 行不属于本次盘点客户。").format(row.idx))
			if flt(row.actual_roll_count) < 0 or flt(row.actual_qty) < 0:
				frappe.throw(_("第 {0} 行实盘匹数和重量不能小于 0。").format(row.idx))
			if flt(row.actual_roll_count) != cint(row.actual_roll_count):
				frappe.throw(_("第 {0} 行实盘匹数必须为整数。").format(row.idx))
			row.difference_roll_count = flt(row.actual_roll_count) - flt(row.system_roll_count)
			row.difference_qty = flt(row.actual_qty) - flt(row.system_qty)
			if (_has_difference(row.difference_roll_count) or _has_difference(row.difference_qty)) and not row.difference_reason:
				frappe.throw(_("第 {0} 行存在盘点差异，请选择差异原因。").format(row.idx))

	def _set_totals(self):
		for target, source in (
			("total_system_roll_count", "system_roll_count"),
			("total_actual_roll_count", "actual_roll_count"),
			("total_difference_roll_count", "difference_roll_count"),
			("total_system_qty", "system_qty"),
			("total_actual_qty", "actual_qty"),
			("total_difference_qty", "difference_qty"),
		):
			self.set(target, sum(flt(row.get(source)) for row in self.items))
		self._set_list_summaries()

	def _set_list_summaries(self):
		self.customer_name = _summarize_distinct(self.items, "customer_name")
		self.batch_summary = _summarize_distinct(self.items, "batch_no")
		self.item_name_summary = _summarize_distinct(self.items, "item_name")
		self.difference_reason_summary = _summarize_distinct(self.items, "difference_reason")

	def _assert_snapshot_is_current(self):
		current = {(row.batch_no, row.source_warehouse): row for row in _scope_stock_rows(self.warehouse, self.customer)}
		snapshot_keys = {(row.batch_no, row.stock_warehouse) for row in self.items}
		changed = []
		for row in self.items:
			stock = current.get((row.batch_no, row.stock_warehouse))
			current_rolls = flt(stock.stock_roll_count) if stock else 0
			current_qty = flt(stock.stock_qty) if stock else 0
			if _has_difference(current_rolls - flt(row.system_roll_count)) or _has_difference(current_qty - flt(row.system_qty)):
				changed.append(_("{0}（当前 {1} 匹 / {2} {3}）").format(
					row.batch_no, current_rolls, current_qty, row.stock_uom or "",
				))
		for key, stock in current.items():
			if key not in snapshot_keys:
				changed.append(_("{0}（盘点期间新增库存）").format(stock.batch_no))
		if changed:
			frappe.throw(_("盘点期间账面库存已变化，请取消提交并重新读取库存：<br>{0}").format("<br>".join(changed)))

	def _create_stock_reconciliation(self):
		rows = [row for row in self.items if _has_difference(row.difference_qty)]
		if not rows:
			return None

		company = frappe.db.get_value("Warehouse", self.warehouse, "company")
		if not company:
			frappe.throw(_("盘点仓库/货位未设置公司。"))

		reconciliation = frappe.get_doc({
			"doctype": "Stock Reconciliation",
			"purpose": "Stock Reconciliation",
			"company": company,
			"posting_date": self.count_date,
			"posting_time": self.posting_time,
			"set_posting_time": 1,
			"items": [{
				"item_code": row.item_code,
				"warehouse": row.stock_warehouse,
				"qty": flt(row.actual_qty),
				"stock_uom": row.stock_uom,
				"batch_no": row.batch_no,
				"use_serial_batch_fields": 1,
				"allow_zero_valuation_rate": 1,
			} for row in rows],
		})
		reconciliation.insert(ignore_permissions=True)
		reconciliation.submit()
		reconciliation.add_comment("Info", _("由胚布盘点表 {0} 审核生成。").format(self.name))
		return reconciliation


def _has_difference(value):
	return abs(flt(value)) > TOLERANCE


def _summarize_distinct(rows, fieldname, limit=3):
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
		frappe.throw(_("只有库存经理或系统经理可以审核胚布盘点差异。"), frappe.PermissionError)


def _lock_inventory_count(name):
	if not frappe.db.sql(
		"SELECT name FROM `tabGrey Fabric Inventory Count` WHERE name=%s FOR UPDATE", name
	):
		frappe.throw(_("胚布盘点表 {0} 不存在。").format(name))
	return frappe.get_doc("Grey Fabric Inventory Count", name)


@frappe.whitelist()
def approve_inventory_count(name, review_remark=None):
	_assert_can_review()
	doc = _lock_inventory_count(name)
	if doc.docstatus != 1:
		frappe.throw(_("只能审核已提交的胚布盘点表。"))
	if doc.status == "已审核":
		return {"status": doc.status, "stock_reconciliation": doc.stock_reconciliation}
	if doc.status != "待审核":
		frappe.throw(_("当前状态为 {0}，不能审核通过。").format(doc.status))

	doc._assert_snapshot_is_current()
	reconciliation = doc._create_stock_reconciliation()
	doc.db_set({
		"status": "已审核",
		"reviewed_by": frappe.session.user,
		"reviewed_at": now(),
		"review_remark": review_remark or None,
		"stock_reconciliation": reconciliation.name if reconciliation else None,
	})
	doc.add_comment(
		"Info",
		_("盘点差异已由 {0} 审核通过。库存调整凭证：{1}").format(
			frappe.session.user, reconciliation.name if reconciliation else _("无重量差异，无需生成")
		),
	)
	return {"status": "已审核", "stock_reconciliation": reconciliation.name if reconciliation else None}


@frappe.whitelist()
def reject_inventory_count(name, review_remark):
	_assert_can_review()
	if not (review_remark or "").strip():
		frappe.throw(_("驳回盘点差异时必须填写审核意见。"))
	doc = _lock_inventory_count(name)
	if doc.docstatus != 1 or doc.status != "待审核":
		frappe.throw(_("只有待审核的已提交盘点表可以驳回。"))
	doc.db_set({
		"status": "已驳回",
		"reviewed_by": frappe.session.user,
		"reviewed_at": now(),
		"review_remark": review_remark.strip(),
	})
	doc.add_comment("Info", _("盘点差异已由 {0} 驳回：{1}").format(frappe.session.user, review_remark.strip()))
	return {"status": "已驳回"}


def _warehouse_in_scope(stock_warehouse, selected_warehouse):
	return stock_warehouse in _scope_warehouse_names(selected_warehouse)


def _main_grey_fabric_warehouse_names():
	"""Return the normal grey-fabric warehouse and its permitted location leaves."""
	default_warehouse = get_setting("grey_fabric_warehouse")
	default = frappe.db.get_value(
		"Warehouse", default_warehouse, ["warehouse_name", "company"], as_dict=True
	)
	if not default:
		return tuple()
	location_group_name = (default.warehouse_name or "").replace("仓库", "货位")
	warehouses = [default_warehouse]
	if location_group_name:
		rows = frappe.db.sql("""
			SELECT child.name
			FROM `tabWarehouse` child
			INNER JOIN `tabWarehouse` location_group ON location_group.name=child.parent_warehouse
			WHERE child.is_group=0 AND child.disabled=0 AND child.company=%(company)s
				AND location_group.warehouse_name=%(location_group_name)s
			ORDER BY child.name
		""", {"company": default.company, "location_group_name": location_group_name}, as_dict=True)
		warehouses.extend(row.name for row in rows)
	return tuple(dict.fromkeys(warehouses))


def _inventory_count_warehouse_names():
	"""Return warehouses that may be selected for a grey-fabric inventory count."""
	warehouses = list(_main_grey_fabric_warehouse_names())
	return_rework_warehouse = get_setting("return_rework_warehouse")
	if return_rework_warehouse:
		warehouses.append(return_rework_warehouse)
	return tuple(dict.fromkeys(warehouses))


def _scope_warehouse_names(selected_warehouse):
	if selected_warehouse == get_setting("grey_fabric_warehouse"):
		return _main_grey_fabric_warehouse_names()
	if selected_warehouse in _inventory_count_warehouse_names():
		return (selected_warehouse,)
	return tuple()


def _customer_scopes_overlap(left_customer, right_customer):
	return not left_customer or not right_customer or left_customer == right_customer


def _find_overlapping_inventory_count(name, warehouse, customer=None):
	selected_scope = set(_scope_warehouse_names(warehouse))
	if not selected_scope:
		return None
	active_counts = frappe.get_all(
		"Grey Fabric Inventory Count",
		filters={"name": ["!=", name or ""], "docstatus": ["in", [0, 1]]},
		fields=["name", "warehouse", "customer", "docstatus", "status"],
		order_by="creation asc",
	)
	for count in active_counts:
		if cint(count.docstatus) == 1 and count.status != "待审核":
			continue
		if not selected_scope.intersection(_scope_warehouse_names(count.warehouse)):
			continue
		if _customer_scopes_overlap(customer, count.customer):
			return count.name
	return None


def _scope_stock_rows(warehouse, customer=None):
	return [row for row in _available_rows(customer) if _warehouse_in_scope(row.source_warehouse, warehouse)]


def _batch_details(batch_no):
	return frappe.db.get_value(
		"Customer Grey Fabric Receipt Item",
		{"batch_no": batch_no, "docstatus": 1},
		["barcode", "width", "gsm"],
		as_dict=True,
	) or {}


@frappe.whitelist()
def get_inventory_count_rows(warehouse, customer=None):
	if not warehouse:
		frappe.throw(_("请先选择盘点仓库/货位。"))
	rows = []
	for stock in _scope_stock_rows(warehouse, customer):
		details = _batch_details(stock.batch_no)
		rows.append({
			"customer": stock.customer,
			"customer_name": stock.customer_name,
			"item_code": stock.item_code,
			"item_name": stock.item_name,
			"batch_no": stock.batch_no,
			"barcode": details.get("barcode"),
			"color": stock.color,
			"width": details.get("width"),
			"gsm": details.get("gsm"),
			"stock_warehouse": stock.source_warehouse,
			"stock_uom": frappe.db.get_value("Item", stock.item_code, "stock_uom"),
			"system_roll_count": flt(stock.stock_roll_count),
			"actual_roll_count": flt(stock.stock_roll_count),
			"difference_roll_count": 0,
			"system_qty": flt(stock.stock_qty),
			"actual_qty": flt(stock.stock_qty),
			"difference_qty": 0,
		})
	return {"snapshot_at": now(), "items": rows}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_grey_fabric_warehouses(doctype, txt, searchfield, start, page_len, filters=None):
	"""Link-field query: show normal grey-fabric locations and the rework holding warehouse."""
	warehouses = _inventory_count_warehouse_names()
	if not warehouses:
		return []
	rows = frappe.db.sql("""
		SELECT name, warehouse_name
		FROM `tabWarehouse`
		WHERE name IN %(warehouses)s AND is_group=0 AND disabled=0
			AND (name LIKE %(txt)s OR warehouse_name LIKE %(txt)s)
		ORDER BY CASE
			WHEN name=%(default_warehouse)s THEN 0
			WHEN name=%(return_rework_warehouse)s THEN 2
			ELSE 1
		END, warehouse_name
		LIMIT %(start)s, %(page_len)s
	""", {
		"warehouses": warehouses,
		"txt": f"%{txt or ''}%",
		"default_warehouse": get_setting("grey_fabric_warehouse"),
		"return_rework_warehouse": get_setting("return_rework_warehouse"),
		"start": cint(start),
		"page_len": cint(page_len),
	})
	return rows
