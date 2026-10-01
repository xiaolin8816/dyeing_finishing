import frappe
from frappe import _


def execute(filters=None):
    columns = [
        {"label": _("客户"), "fieldname": "customer", "fieldtype": "Data", "width": 170},
        {"label": _("批次"), "fieldname": "batch_no", "fieldtype": "Data", "width": 145},
        {"label": _("胚布名称"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": _("库存匹数"), "fieldname": "stock_roll_count", "fieldtype": "Float", "precision": 2, "width": 110},
        {"label": _("库存数量"), "fieldname": "stock_qty", "fieldtype": "Float", "precision": 2, "width": 110},
        {"label": _("入库匹数"), "fieldname": "receipt_roll_count", "fieldtype": "Float", "precision": 2, "width": 110},
        {"label": _("入库数量"), "fieldname": "receipt_qty", "fieldtype": "Float", "precision": 2, "width": 110},
        {"label": _("出库匹数"), "fieldname": "issue_roll_count", "fieldtype": "Float", "precision": 2, "width": 110},
        {"label": _("出库数量"), "fieldname": "issue_qty", "fieldtype": "Float", "precision": 2, "width": 110},
        {"label": _("单位"), "fieldname": "stock_uom", "fieldtype": "Data", "width": 75},
        {"label": _("货位编号"), "fieldname": "location", "fieldtype": "Data", "width": 180},
        {"label": _("仓库"), "fieldname": "warehouse", "fieldtype": "Data", "width": 150},
        {"label": _("入库日期"), "fieldname": "receipt_date", "fieldtype": "Date", "width": 100},
        {"label": _("颜色"), "fieldname": "color", "fieldtype": "Data", "width": 100},
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
            SUM(sle.actual_qty) AS stock_qty,
            COALESCE(MAX(receipt_rolls.receipt_roll_count), 0) AS receipt_roll_count,
            COALESCE(MAX(receipt_rolls.receipt_qty), 0) AS receipt_qty,
            COALESCE(MAX(issued_rolls.issue_roll_count), 0) AS issue_roll_count,
            COALESCE(MAX(issued_rolls.issue_qty), 0) AS issue_qty,
            MAX(item.stock_uom) AS stock_uom, MAX(receipt.receipt_date) AS receipt_date
        FROM `tabStock Ledger Entry` sle
        INNER JOIN `tabItem` item ON item.name = sle.item_code
        LEFT JOIN `tabWarehouse` stock_warehouse ON stock_warehouse.name = sle.warehouse
        LEFT JOIN `tabSerial and Batch Entry` bundle_entry ON bundle_entry.parent = sle.serial_and_batch_bundle
        LEFT JOIN `tabCustomer Grey Fabric Receipt Item` receipt_item
            ON receipt_item.batch_no = COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no)
        LEFT JOIN `tabCustomer Grey Fabric Receipt` receipt
            ON receipt.name = receipt_item.parent AND receipt.docstatus = 1
        LEFT JOIN (
            SELECT receipt_item.batch_no,
                SUM(receipt_item.roll_count) AS receipt_roll_count,
                SUM(receipt_item.weight_qty) AS receipt_qty,
                SUM(receipt_item.roll_count) AS stock_roll_count
            FROM `tabCustomer Grey Fabric Receipt Item` receipt_item
            INNER JOIN `tabCustomer Grey Fabric Receipt` receipt
                ON receipt.name = receipt_item.parent AND receipt.docstatus = 1
            WHERE receipt_item.batch_no IS NOT NULL AND receipt_item.batch_no != ''
            GROUP BY receipt_item.batch_no
        ) receipt_rolls ON receipt_rolls.batch_no = COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no)
        LEFT JOIN (
            SELECT issue_item.batch_no,
                SUM(issue_item.issue_roll_count) AS issue_roll_count,
                SUM(issue_item.issue_qty) AS issue_qty
            FROM `tabGrey Fabric Issue Item` issue_item
            INNER JOIN `tabGrey Fabric Issue` issue ON issue.name = issue_item.parent AND issue.docstatus = 1
            GROUP BY issue_item.batch_no
        ) issued_rolls ON issued_rolls.batch_no = COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no)
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
          AND sle.warehouse != '生产中转仓 - 沅泰'
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
