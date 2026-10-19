import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("生产流转卡"), "fieldname": "flow_card", "fieldtype": "Link", "options": "Production Flow Card", "width": 125},
		{"label": _("染整销售订单"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Dyeing Sales Order", "width": 130},
		{"label": _("客户名称"), "fieldname": "customer_name", "fieldtype": "Data", "width": 140},
		{"label": _("成品名称"), "fieldname": "finished_product_name", "fieldtype": "Data", "width": 150},
		{"label": _("色号"), "fieldname": "color_no", "fieldtype": "Link", "options": "Color Master", "width": 90},
		{"label": _("颜色"), "fieldname": "color", "fieldtype": "Data", "width": 90},
		{"label": _("交货日期"), "fieldname": "delivery_date", "fieldtype": "Date", "width": 105},
		{"label": _("订单数量"), "fieldname": "order_qty", "fieldtype": "Float", "precision": 3, "width": 105},
		{"label": _("生产状态"), "fieldname": "production_status", "fieldtype": "Data", "width": 90},
		{"label": _("当前进度状态"), "fieldname": "current_progress_status", "fieldtype": "Data", "width": 120},
		{"label": _("当前工序"), "fieldname": "current_operation", "fieldtype": "Link", "options": "Production Operation", "width": 110},
		{"label": _("工序完成数"), "fieldname": "completed_operation_count", "fieldtype": "Int", "width": 95},
		{"label": _("工序总数"), "fieldname": "operation_count", "fieldtype": "Int", "width": 85},
		{"label": _("胚布出库重量"), "fieldname": "grey_issue_qty", "fieldtype": "Float", "precision": 3, "width": 115},
		{"label": _("累计入库次数"), "fieldname": "packing_receipt_count", "fieldtype": "Int", "width": 105},
		{"label": _("累计入库匹数"), "fieldname": "packed_roll_count", "fieldtype": "Int", "width": 105},
		{"label": _("累计入库重量"), "fieldname": "packed_weight", "fieldtype": "Float", "precision": 3, "width": 110},
		{"label": _("累计入库码数"), "fieldname": "packed_yard_qty", "fieldtype": "Float", "precision": 3, "width": 110},
		{"label": _("包装完成率"), "fieldname": "packing_completion_rate", "fieldtype": "Percent", "width": 105},
		{"label": _("累计出库次数"), "fieldname": "delivery_count", "fieldtype": "Int", "width": 105},
		{"label": _("累计出库匹数"), "fieldname": "delivered_roll_count", "fieldtype": "Int", "width": 105},
		{"label": _("累计出库重量"), "fieldname": "delivered_weight", "fieldtype": "Float", "precision": 3, "width": 110},
		{"label": _("累计出库码数"), "fieldname": "delivered_yard_qty", "fieldtype": "Float", "precision": 3, "width": 110},
		{"label": _("待出库匹数"), "fieldname": "remaining_roll_count", "fieldtype": "Int", "width": 100},
		{"label": _("待出库重量"), "fieldname": "remaining_weight", "fieldtype": "Float", "precision": 3, "width": 105},
		{"label": _("待出库码数"), "fieldname": "remaining_yard_qty", "fieldtype": "Float", "precision": 3, "width": 105},
		{"label": _("出库完成率"), "fieldname": "delivery_completion_rate", "fieldtype": "Percent", "width": 105},
		{"label": _("最近入库日期"), "fieldname": "last_receipt_date", "fieldtype": "Date", "width": 110},
		{"label": _("最近出库日期"), "fieldname": "last_delivery_date", "fieldtype": "Date", "width": 110},
		{"label": _("入出库进度"), "fieldname": "completion_status", "fieldtype": "Data", "width": 100},
		{"label": _("是否逾期"), "fieldname": "is_overdue", "fieldtype": "Data", "width": 80},
	]


def get_data(filters):
	conditions = ["card.docstatus < 2"]
	values = {}
	for field, expression in (
		("customer", "card.customer"),
		("sales_order", "card.sales_order"),
		("flow_card", "card.name"),
		("production_status", "card.production_status"),
		("current_progress_status", "card.current_progress_status"),
		("current_operation", "card.current_operation"),
	):
		if filters.get(field):
			conditions.append(f"{expression} = %({field})s")
			values[field] = filters[field]
	if filters.get("from_date"):
		conditions.append("card.delivery_date >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("card.delivery_date <= %(to_date)s")
		values["to_date"] = filters.to_date

	rows = frappe.db.sql(
		f"""
		SELECT card.name AS flow_card, card.sales_order, card.customer,
			COALESCE(customer.customer_name, card.customer) AS customer_name,
			card.finished_product_name, card.color_no, card.color, card.delivery_date,
			card.order_qty, card.production_status, card.current_progress_status,
			card.current_operation,
			COALESCE(operations.operation_count, 0) AS operation_count,
			COALESCE(operations.completed_operation_count, 0) AS completed_operation_count,
			COALESCE(grey.grey_issue_qty, 0) AS grey_issue_qty,
			COALESCE(packing.packing_receipt_count, 0) AS packing_receipt_count,
			COALESCE(packing.packed_roll_count, 0) AS packed_roll_count,
			COALESCE(packing.packed_weight, 0) AS packed_weight,
			COALESCE(packing.packed_yard_qty, 0) AS packed_yard_qty,
			packing.last_receipt_date,
			COALESCE(delivery.delivery_count, 0) AS delivery_count,
			COALESCE(delivery.delivered_roll_count, 0) AS delivered_roll_count,
			COALESCE(delivery.delivered_weight, 0) AS delivered_weight,
			COALESCE(delivery.delivered_yard_qty, 0) AS delivered_yard_qty,
			delivery.last_delivery_date
		FROM `tabProduction Flow Card` card
		LEFT JOIN `tabCustomer` customer ON customer.name = card.customer
		LEFT JOIN (
			SELECT parent, COUNT(*) AS operation_count,
				SUM(CASE WHEN operation_status = '已完成' THEN 1 ELSE 0 END) AS completed_operation_count
			FROM `tabProduction Flow Card Operation`
			GROUP BY parent
		) operations ON operations.parent = card.name
		LEFT JOIN (
			SELECT flow_card, SUM(issue_qty) AS grey_issue_qty
			FROM `tabGrey Fabric Issue`
			WHERE docstatus = 1
			GROUP BY flow_card
		) grey ON grey.flow_card = card.name
		LEFT JOIN (
			SELECT production_flow_card, COUNT(*) AS packing_receipt_count,
				SUM(total_roll_count) AS packed_roll_count, SUM(total_weight) AS packed_weight,
				SUM(total_yard_qty) AS packed_yard_qty, MAX(packing_date) AS last_receipt_date
			FROM `tabFinished Product Packing Receipt`
			WHERE docstatus = 1 AND packing_status = '已入库'
			GROUP BY production_flow_card
		) packing ON packing.production_flow_card = card.name
		LEFT JOIN (
			SELECT production_flow_card, COUNT(*) AS delivery_count,
				SUM(total_roll_count) AS delivered_roll_count, SUM(total_weight) AS delivered_weight,
				SUM(total_yard_qty) AS delivered_yard_qty, MAX(delivery_date) AS last_delivery_date
			FROM `tabFinished Product Delivery`
			WHERE docstatus = 1 AND delivery_status = '已出库'
			GROUP BY production_flow_card
		) delivery ON delivery.production_flow_card = card.name
		WHERE {' AND '.join(conditions)}
		ORDER BY card.delivery_date ASC, card.name DESC
		""",
		values,
		as_dict=True,
	)

	today = getdate(nowdate())
	result = []
	for row in rows:
		row.packing_completion_rate = min(flt(row.packed_weight) / flt(row.grey_issue_qty) * 100, 100) if flt(row.grey_issue_qty) else 0
		row.remaining_roll_count = max(cint(row.packed_roll_count) - cint(row.delivered_roll_count), 0)
		row.remaining_weight = max(flt(row.packed_weight) - flt(row.delivered_weight), 0)
		row.remaining_yard_qty = max(flt(row.packed_yard_qty) - flt(row.delivered_yard_qty), 0)
		row.delivery_completion_rate = min(flt(row.delivered_weight) / flt(row.packed_weight) * 100, 100) if flt(row.packed_weight) else 0
		row.completion_status = _completion_status(row)
		is_finished = row.completion_status == "全部出库"
		row.is_overdue = "是" if row.delivery_date and getdate(row.delivery_date) < today and not is_finished else "否"
		if filters.get("completion_status") and row.completion_status != filters.completion_status:
			continue
		if cint(filters.get("overdue_only")) and row.is_overdue != "是":
			continue
		result.append(row)
	return result


def _completion_status(row):
	if flt(row.delivered_weight) > 0:
		return "全部出库" if flt(row.remaining_weight) <= 0.000001 and flt(row.grey_issue_qty) <= flt(row.packed_weight) + 0.000001 else "部分出库"
	if flt(row.packed_weight) > 0:
		return "全部入库" if flt(row.grey_issue_qty) <= flt(row.packed_weight) + 0.000001 else "部分入库"
	return "未入库"


@frappe.whitelist()
def get_progress_details(flow_card):
	if not flow_card or not frappe.db.exists("Production Flow Card", flow_card):
		frappe.throw(_("生产流转卡不存在"))
	if not frappe.has_permission("Production Flow Card", "read", flow_card):
		frappe.throw(_("没有权限查看该生产流转卡"), frappe.PermissionError)

	progress = frappe.get_all(
		"Production Flow Card Progress",
		filters={"parent": flow_card, "parenttype": "Production Flow Card"},
		fields=["progress_time", "operation", "progress_status", "source_doctype", "source_document",
			"quantity", "uom", "roll_count", "yard_qty", "operator", "description"],
		order_by="progress_time desc, creation desc",
	)
	operations = frappe.get_all(
		"Production Flow Card Operation",
		filters={"parent": flow_card, "parenttype": "Production Flow Card"},
		fields=["sequence_no", "operation", "operation_name", "operation_status", "job_card"],
		order_by="sequence_no asc, idx asc",
	)
	material_sheets = _get_dyeing_material_summary(flow_card)
	related_sheet_names = [row.name for row in material_sheets]
	for operation in operations:
		operation["related_material_sheets"] = related_sheet_names if "染色" in (operation.operation_name or "") else []
	packing = frappe.get_all(
		"Finished Product Packing Receipt",
		filters={"production_flow_card": flow_card, "docstatus": ["<", 2]},
		fields=["name", "packing_date", "packing_status", "total_roll_count", "total_weight", "total_yard_qty", "stock_entry"],
		order_by="packing_date desc, creation desc",
	)
	delivery = frappe.get_all(
		"Finished Product Delivery",
		filters={"production_flow_card": flow_card, "docstatus": ["<", 2]},
		fields=["name", "delivery_date", "delivery_status", "total_roll_count", "total_weight", "total_yard_qty", "stock_entry"],
		order_by="delivery_date desc, creation desc",
	)
	return {
		"progress": progress,
		"operations": operations,
		"dyeing_materials": material_sheets,
		"packing": packing,
		"delivery": delivery,
	}


def _get_dyeing_material_summary(flow_card):
	if not frappe.has_permission("Site Dyeing Material Sheet", "read"):
		return []
	sheets = frappe.get_all(
		"Site Dyeing Material Sheet",
		filters={"production_flow_card": flow_card, "docstatus": ["<", 2]},
		fields=["name", "dyeing_sequence", "material_sheet_type", "material_sheet_status", "laboratory_recipe",
			"recipe_version", "production_resource", "planned_dyeing_date"],
		order_by="dyeing_sequence asc, creation asc",
	)
	for sheet in sheets:
		quantity = frappe.db.sql(
			"""SELECT COALESCE(SUM(actual_qty), 0) AS planned_qty_g,
				COALESCE(SUM(issued_qty), 0) AS issued_qty_g
			FROM `tabSite Dyeing Material Sheet Item` WHERE parent = %s""",
			sheet.name,
			as_dict=True,
		)[0]
		issue = frappe.db.sql(
			"""SELECT COUNT(*) AS issue_count, MAX(name) AS latest_issue
			FROM `tabSite Dyeing Material Issue`
			WHERE material_sheet = %s AND docstatus = 1""",
			sheet.name,
			as_dict=True,
		)[0]
		sheet.planned_qty_g = flt(quantity.planned_qty_g)
		sheet.issued_qty_g = flt(quantity.issued_qty_g)
		sheet.remaining_qty_g = max(sheet.planned_qty_g - sheet.issued_qty_g, 0)
		sheet.issue_count = cint(issue.issue_count)
		sheet.latest_issue = issue.latest_issue or ""
	return sheets
