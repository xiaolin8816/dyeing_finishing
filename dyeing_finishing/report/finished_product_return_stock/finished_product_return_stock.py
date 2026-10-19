import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = ["parent.docstatus = 1", "parent.return_status = '已收货待检'"]
	values = {}
	for fieldname, expression in (
		("company", "warehouse.company"),
		("warehouse", "parent.target_warehouse"),
		("customer", "parent.customer"),
		("production_flow_card", "parent.production_flow_card"),
		("return_document", "parent.name"),
		("return_reason", "parent.return_reason"),
		("inspection_status", "item.inspection_status"),
	):
		if filters.get(fieldname):
			conditions.append(f"{expression} = %({fieldname})s")
			values[fieldname] = filters[fieldname]
	if filters.get("from_date"):
		conditions.append("parent.return_date >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("parent.return_date <= %(to_date)s")
		values["to_date"] = filters.to_date

	columns = [
		{"label": _("生产流转卡"), "fieldname": "production_flow_card", "fieldtype": "Link", "options": "Production Flow Card", "width": 120},
		{"label": _("客户名称"), "fieldname": "customer_name", "fieldtype": "Data", "width": 140},
		{"label": _("染整销售订单"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Dyeing Sales Order", "width": 140},
		{"label": _("成品名称"), "fieldname": "finished_product_name", "fieldtype": "Data", "width": 150},
		{"label": _("色号"), "fieldname": "color_no", "fieldtype": "Data", "width": 85},
		{"label": _("颜色"), "fieldname": "color", "fieldtype": "Data", "width": 85},
		{"label": _("成品规格"), "fieldname": "finished_specification", "fieldtype": "Data", "width": 140},
		{"label": _("成品批次"), "fieldname": "finished_batch_no", "fieldtype": "Link", "options": "Batch", "width": 130},
		{"label": _("匹号"), "fieldname": "piece_no", "fieldtype": "Data", "width": 70},
		{"label": _("成品卷号"), "fieldname": "roll_no", "fieldtype": "Data", "width": 150},
		{"label": _("退货处理单"), "fieldname": "return_document", "fieldtype": "Link", "options": "Finished Product Return", "width": 135},
		{"label": _("原成品出库单"), "fieldname": "source_delivery", "fieldtype": "Link", "options": "Finished Product Delivery", "width": 135},
		{"label": _("退货日期"), "fieldname": "return_date", "fieldtype": "Date", "width": 100},
		{"label": _("退货原因"), "fieldname": "return_reason", "fieldtype": "Data", "width": 95},
		{"label": _("当前仓库"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"label": _("检验状态"), "fieldname": "inspection_status", "fieldtype": "Data", "width": 90},
		{"label": _("处置结论"), "fieldname": "disposal_decision", "fieldtype": "Data", "width": 105},
		{"label": _("待处理重量(Kg)"), "fieldname": "pending_weight", "fieldtype": "Float", "precision": 3, "width": 125},
		{"label": _("待处理码数(Y)"), "fieldname": "pending_yard_qty", "fieldtype": "Float", "precision": 3, "width": 125},
		{"label": _("库存天数"), "fieldname": "stock_days", "fieldtype": "Data", "width": 85},
		{"label": _("退货入库凭证"), "fieldname": "stock_entry", "fieldtype": "Link", "options": "Stock Entry", "width": 135},
	]

	data = frappe.db.sql(
		f"""SELECT parent.production_flow_card, parent.customer_name, parent.sales_order,
			parent.finished_product_name, parent.color_no, parent.color,
			parent.finished_specification, parent.finished_batch_no,
			CAST(item.piece_no AS CHAR) AS piece_no, item.roll_no,
			parent.name AS return_document, item.source_delivery, parent.return_date,
			parent.return_reason, parent.target_warehouse AS warehouse,
			item.inspection_status, item.disposal_decision,
			GREATEST(item.return_weight-COALESCE(moved.weight,0),0) AS pending_weight,
			GREATEST(item.return_yard_qty-COALESCE(moved.yards,0),0) AS pending_yard_qty,
			CAST(DATEDIFF(CURDATE(), parent.return_date) AS CHAR) AS stock_days,
			parent.stock_entry
		FROM `tabFinished Product Return Item` item
		INNER JOIN `tabFinished Product Return` parent ON parent.name = item.parent
		LEFT JOIN `tabWarehouse` warehouse ON warehouse.name = parent.target_warehouse
		LEFT JOIN (
			SELECT child.return_item, SUM(child.transfer_weight) AS weight, SUM(child.transfer_yard_qty) AS yards
			FROM `tabFinished Product Return to Grey Fabric Item` child
			INNER JOIN `tabFinished Product Return to Grey Fabric` transfer ON transfer.name=child.parent
			WHERE transfer.docstatus=1 GROUP BY child.return_item
		) moved ON moved.return_item=item.name
		WHERE {' AND '.join(conditions)}
		  AND (item.return_weight-COALESCE(moved.weight,0) > 0.000001 OR item.return_yard_qty-COALESCE(moved.yards,0) > 0.000001)
		ORDER BY parent.return_date DESC, parent.creation DESC, item.idx""",
		values,
		as_dict=True,
	)
	return columns, data
