import frappe
from frappe import _


def execute(filters=None):
    columns = [
        {"label": _("胚布编码"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
        {"label": _("胚布名称"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": _("批次"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 145},
        {"label": _("客户"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 170},
        {"label": _("颜色"), "fieldname": "color", "fieldtype": "Data", "width": 100},
        {"label": _("门幅"), "fieldname": "width", "fieldtype": "Data", "width": 90},
        {"label": _("克重"), "fieldname": "gsm", "fieldtype": "Data", "width": 90},
        {"label": _("仓库"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
        {"label": _("库存货位"), "fieldname": "location", "fieldtype": "Link", "options": "Warehouse", "width": 180},
        {"label": _("库存匹数"), "fieldname": "stock_roll_count", "fieldtype": "Float", "precision": 2, "width": 110},
        {"label": _("库存重量"), "fieldname": "stock_qty", "fieldtype": "Float", "precision": 2, "width": 110},
        {"label": _("单位"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 75},
        {"label": _("入库日期"), "fieldname": "receipt_date", "fieldtype": "Date", "width": 100},
    ]
    data = frappe.db.sql("""
        SELECT sle.item_code, item.item_name,
            COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no) AS batch_no,
            MAX(receipt.customer) AS customer, MAX(receipt_item.color) AS color,
            MAX(receipt_item.width) AS width, MAX(receipt_item.gsm) AS gsm,
            CASE
                WHEN stock_warehouse.parent_warehouse = '胚布货位 - 沅泰' THEN '胚布仓库 - 沅泰'
                ELSE sle.warehouse
            END AS warehouse,
            CASE
                WHEN stock_warehouse.parent_warehouse = '胚布货位 - 沅泰' THEN sle.warehouse
                ELSE NULL
            END AS location,
            CASE
                WHEN sle.warehouse = '生产中转仓 - 沅泰' THEN GREATEST(COALESCE(MAX(transfer_rolls.roll_delta), 0), 0)
                ELSE GREATEST(
                    COALESCE(MAX(receipt_rolls.stock_roll_count), 0)
                    + COALESCE(MAX(transfer_rolls.roll_delta), 0),
                    0
                )
            END AS stock_roll_count,
            SUM(sle.actual_qty) AS stock_qty, MAX(item.stock_uom) AS stock_uom,
            MAX(receipt.receipt_date) AS receipt_date
        FROM `tabStock Ledger Entry` sle
        INNER JOIN `tabItem` item ON item.name = sle.item_code
        LEFT JOIN `tabWarehouse` stock_warehouse ON stock_warehouse.name = sle.warehouse
        LEFT JOIN `tabSerial and Batch Entry` bundle_entry ON bundle_entry.parent = sle.serial_and_batch_bundle
        LEFT JOIN `tabCustomer Grey Fabric Receipt Item` receipt_item
            ON receipt_item.batch_no = COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no)
        LEFT JOIN `tabCustomer Grey Fabric Receipt` receipt
            ON receipt.name = receipt_item.parent AND receipt.docstatus = 1
        LEFT JOIN (
            SELECT receipt_item.batch_no, SUM(receipt_item.roll_count) AS stock_roll_count
            FROM `tabCustomer Grey Fabric Receipt Item` receipt_item
            INNER JOIN `tabCustomer Grey Fabric Receipt` receipt
                ON receipt.name = receipt_item.parent AND receipt.docstatus = 1
            WHERE receipt_item.batch_no IS NOT NULL AND receipt_item.batch_no != ''
            GROUP BY receipt_item.batch_no
        ) receipt_rolls ON receipt_rolls.batch_no = COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no)
        LEFT JOIN (
            SELECT item_code, batch_no, warehouse, SUM(roll_delta) AS roll_delta
            FROM (
                SELECT detail.item_code, detail.batch_no, detail.t_warehouse AS warehouse,
                    SUM(detail.custom_roll_count) AS roll_delta
                FROM `tabStock Entry Detail` detail
                INNER JOIN `tabStock Entry` entry ON entry.name = detail.parent AND entry.docstatus = 1
                WHERE detail.batch_no IS NOT NULL AND detail.batch_no != ''
                  AND detail.t_warehouse IS NOT NULL AND detail.t_warehouse != ''
                  AND detail.custom_roll_count != 0
                GROUP BY detail.item_code, detail.batch_no, detail.t_warehouse
                UNION ALL
                SELECT detail.item_code, detail.batch_no, detail.s_warehouse AS warehouse,
                    -SUM(detail.custom_roll_count) AS roll_delta
                FROM `tabStock Entry Detail` detail
                INNER JOIN `tabStock Entry` entry ON entry.name = detail.parent AND entry.docstatus = 1
                WHERE detail.batch_no IS NOT NULL AND detail.batch_no != ''
                  AND detail.s_warehouse IS NOT NULL AND detail.s_warehouse != ''
                  AND detail.custom_roll_count != 0
                GROUP BY detail.item_code, detail.batch_no, detail.s_warehouse
            ) roll_movements
            GROUP BY item_code, batch_no, warehouse
        ) transfer_rolls
            ON transfer_rolls.item_code = sle.item_code
            AND transfer_rolls.batch_no = COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no)
            AND transfer_rolls.warehouse = sle.warehouse
        WHERE sle.is_cancelled = 0
          AND COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no) IS NOT NULL
          AND COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no) != ''
          AND item.item_group IN (
            SELECT name FROM `tabItem Group`
            WHERE lft >= (SELECT lft FROM `tabItem Group` WHERE name = '胚布')
              AND rgt <= (SELECT rgt FROM `tabItem Group` WHERE name = '胚布')
          )
        GROUP BY sle.item_code, item.item_name,
            COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no), sle.warehouse
        HAVING SUM(sle.actual_qty) > 0
        ORDER BY receipt_date DESC, batch_no DESC
    """, as_dict=True)
    return columns, data
