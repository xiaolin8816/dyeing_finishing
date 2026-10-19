import frappe
from frappe import _
from frappe.utils import cint


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = ["item.custom_is_finished_product = 1"]
	values = {}
	for field, expression in (
		("company", "stock.company"),
		("warehouse", "stock.warehouse"),
		("customer", "packing.customer"),
		("item_code", "stock.item_code"),
		("batch_no", "stock.batch_no"),
		("production_flow_card", "packing.production_flow_card"),
	):
		if filters.get(field):
			conditions.append(f"{expression} = %({field})s")
			values[field] = filters[field]
	if not cint(filters.get("show_zero_stock")):
		conditions.append("stock.stock_qty > 0.000001")

	columns = [
		{"label": _("成品物料编码"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
		{"label": _("成品名称"), "fieldname": "item_name", "fieldtype": "Data", "width": 160},
		{"label": _("色号"), "fieldname": "color_no", "fieldtype": "Data", "width": 90},
		{"label": _("颜色"), "fieldname": "color", "fieldtype": "Data", "width": 90},
		{"label": _("成品规格"), "fieldname": "specification", "fieldtype": "Data", "width": 150},
		{"label": _("客户名称"), "fieldname": "customer_name", "fieldtype": "Data", "width": 140},
		{"label": _("仓库"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
		{"label": _("批次"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 135},
		{"label": _("生产流转卡"), "fieldname": "production_flow_card", "fieldtype": "Link", "options": "Production Flow Card", "width": 120},
		{"label": _("染整销售订单"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Dyeing Sales Order", "width": 130},
		{"label": _("库存匹数"), "fieldname": "roll_count", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": _("库存重量"), "fieldname": "stock_qty", "fieldtype": "Float", "precision": 3, "width": 110},
		{"label": _("重量单位"), "fieldname": "stock_uom", "fieldtype": "Data", "width": 75},
		{"label": _("库存码数"), "fieldname": "yard_qty", "fieldtype": "Float", "precision": 3, "width": 110},
		{"label": _("码数单位"), "fieldname": "yard_uom", "fieldtype": "Data", "width": 75},
		{"label": _("最近入库日期"), "fieldname": "last_receipt_date", "fieldtype": "Date", "width": 110},
	]

	data = frappe.db.sql(
		f"""
		SELECT stock.item_code, item.item_name,
			item.custom_finished_color_no AS color_no,
			item.custom_finished_color AS color,
			item.custom_finished_specification AS specification,
			stock.company, stock.warehouse, stock.batch_no, stock.stock_qty,
			item.stock_uom,
			COALESCE(movement.roll_count, 0) AS roll_count,
			COALESCE(movement.yard_qty, 0) AS yard_qty,
			COALESCE(NULLIF(movement.yard_uom, ''), 'Y') AS yard_uom,
			COALESCE(customer.customer_name, packing.customer) AS customer_name,
			packing.production_flow_card, packing.sales_order,
			packing.last_receipt_date
		FROM (
			SELECT sle.item_code, sle.company, sle.warehouse,
				COALESCE(NULLIF(sle.batch_no, ''), batch_entry.batch_no) AS batch_no,
				SUM(sle.actual_qty) AS stock_qty
			FROM `tabStock Ledger Entry` sle
			LEFT JOIN `tabSerial and Batch Entry` batch_entry
				ON batch_entry.parent = sle.serial_and_batch_bundle
			WHERE sle.is_cancelled = 0
			GROUP BY sle.item_code, sle.company, sle.warehouse,
				COALESCE(NULLIF(sle.batch_no, ''), batch_entry.batch_no)
		) stock
		INNER JOIN `tabItem` item ON item.name = stock.item_code
		LEFT JOIN (
			SELECT item_code, batch_no, warehouse,
				SUM(roll_delta) AS roll_count, SUM(yard_delta) AS yard_qty,
				MAX(yard_uom) AS yard_uom
			FROM (
				SELECT detail.item_code, detail.batch_no, detail.t_warehouse AS warehouse,
					detail.custom_roll_count AS roll_delta,
					detail.custom_yard_qty AS yard_delta,
					detail.custom_yard_uom AS yard_uom
				FROM `tabStock Entry Detail` detail
				INNER JOIN `tabStock Entry` entry ON entry.name = detail.parent AND entry.docstatus = 1
				WHERE COALESCE(detail.t_warehouse, '') != ''
				UNION ALL
				SELECT detail.item_code, detail.batch_no, detail.s_warehouse AS warehouse,
					-detail.custom_roll_count AS roll_delta,
					-detail.custom_yard_qty AS yard_delta,
					detail.custom_yard_uom AS yard_uom
				FROM `tabStock Entry Detail` detail
				INNER JOIN `tabStock Entry` entry ON entry.name = detail.parent AND entry.docstatus = 1
				WHERE COALESCE(detail.s_warehouse, '') != ''
			) movements
			GROUP BY item_code, batch_no, warehouse
		) movement ON movement.item_code = stock.item_code
			AND COALESCE(movement.batch_no, '') = COALESCE(stock.batch_no, '')
			AND movement.warehouse = stock.warehouse
		LEFT JOIN (
			SELECT finished_item_code, finished_batch_no, MAX(customer) AS customer,
				MAX(production_flow_card) AS production_flow_card, MAX(sales_order) AS sales_order,
				MAX(last_receipt_date) AS last_receipt_date
			FROM (
				SELECT finished_item_code, finished_batch_no, customer, production_flow_card,
					sales_order, packing_date AS last_receipt_date
				FROM `tabFinished Product Packing Receipt`
				WHERE docstatus = 1 AND packing_status = '已入库'
				UNION ALL
				SELECT finished_item_code, finished_batch_no, target_customer AS customer,
					production_flow_card, target_sales_order AS sales_order, transfer_date AS last_receipt_date
				FROM `tabFinished Product Customer Transfer`
				WHERE docstatus = 1 AND COALESCE(finished_batch_no, '') != ''
			) sources
			GROUP BY finished_item_code, finished_batch_no
		) packing ON packing.finished_item_code = stock.item_code
			AND packing.finished_batch_no = stock.batch_no
		LEFT JOIN `tabCustomer` customer ON customer.name = packing.customer
		WHERE {' AND '.join(conditions)}
		ORDER BY packing.last_receipt_date DESC, stock.batch_no DESC, stock.item_code
		""",
		values,
		as_dict=True,
	)
	return columns, data
