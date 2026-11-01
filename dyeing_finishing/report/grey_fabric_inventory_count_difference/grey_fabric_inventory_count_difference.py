import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _('胚布盘点表'), "fieldname": "inventory_count", "fieldtype": "Link", "options": "Grey Fabric Inventory Count", "width": 140},
		{"label": _('盘点日期'), "fieldname": "count_date", "fieldtype": "Date", "width": 100},
		{"label": _('状态'), "fieldname": "status", "fieldtype": "Data", "width": 85},
		{"label": _('库存盘点凭证'), "fieldname": "stock_reconciliation", "fieldtype": "Link", "options": "Stock Reconciliation", "width": 145},
		{"label": _('审核人'), "fieldname": "reviewed_by", "fieldtype": "Link", "options": "User", "width": 130},
		{"label": _('审核时间'), "fieldname": "reviewed_at", "fieldtype": "Datetime", "width": 145},
		{"label": _('客户名称'), "fieldname": "customer_name", "fieldtype": "Data", "width": 160},
		{"label": _('批次'), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 145},
		{"label": _('胚布名称'), "fieldname": "item_name", "fieldtype": "Data", "width": 160},
		{"label": _('仓库/货位'), "fieldname": "stock_warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"label": _('账面匹数'), "fieldname": "system_roll_count", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _('实盘匹数'), "fieldname": "actual_roll_count", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _('差异匹数'), "fieldname": "difference_roll_count", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _('账面重量'), "fieldname": "system_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _('实盘重量'), "fieldname": "actual_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _('差异重量'), "fieldname": "difference_qty", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _('单位'), "fieldname": "stock_uom", "fieldtype": "Data", "width": 70},
		{"label": _('差异原因'), "fieldname": "difference_reason", "fieldtype": "Data", "width": 110},
		{"label": _('备注'), "fieldname": "remarks", "fieldtype": "Data", "width": 180},
	]
	conditions = []
	values = {}
	for fieldname, expression in (
		("from_date", "count_doc.count_date >= %(from_date)s"),
		("to_date", "count_doc.count_date <= %(to_date)s"),
		("inventory_count", "count_doc.name = %(inventory_count)s"),
		("warehouse", "count_doc.warehouse = %(warehouse)s"),
		("customer", "detail.customer = %(customer)s"),
		("status", "count_doc.status = %(status)s"),
	):
		if filters.get(fieldname):
			conditions.append(expression)
			values[fieldname] = filters.get(fieldname)
	if filters.get("only_difference"):
		conditions.append("(ABS(detail.difference_roll_count) > 0.000001 OR ABS(detail.difference_qty) > 0.000001)")
	where = " AND ".join(conditions) if conditions else "1=1"
	data = frappe.db.sql(f"""
		SELECT count_doc.name inventory_count, count_doc.count_date, count_doc.status,
			count_doc.stock_reconciliation, count_doc.reviewed_by, count_doc.reviewed_at,
			detail.customer_name, detail.batch_no, detail.item_name, detail.stock_warehouse,
			detail.system_roll_count, detail.actual_roll_count, detail.difference_roll_count,
			detail.system_qty, detail.actual_qty, detail.difference_qty, detail.stock_uom,
			detail.difference_reason, detail.remarks
		FROM `tabGrey Fabric Inventory Count Item` detail
		INNER JOIN `tabGrey Fabric Inventory Count` count_doc ON count_doc.name=detail.parent
		WHERE {where}
		ORDER BY count_doc.count_date DESC, count_doc.name DESC, detail.idx
	""", values, as_dict=True)
	return columns, data
