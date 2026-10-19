import frappe
from frappe import _
from dyeing_finishing.dyeing_finishing.settings import get_setting


def execute(filters=None):
    columns = [
        {"label": _("客户名称"), "fieldname": "customer_name", "fieldtype": "Data", "width": 170},
        {"label": _("库存来源"), "fieldname": "stock_source", "fieldtype": "Data", "width": 120},
        {"label": _("来源生产流转卡"), "fieldname": "source_flow_card", "fieldtype": "Link", "options": "Production Flow Card", "width": 130},
        {"label": _("来源转胚布单"), "fieldname": "source_transfer", "fieldtype": "Data", "width": 145},
        {"label": _("原胚布批次"), "fieldname": "source_batch_no", "fieldtype": "Data", "width": 145},
        {"label": _("批次"), "fieldname": "batch_no", "fieldtype": "Data", "width": 145},
        {"label": _("胚布名称"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": _("胚布门幅"), "fieldname": "width", "fieldtype": "Data", "width": 100},
        {"label": _("胚布克重"), "fieldname": "gsm", "fieldtype": "Data", "width": 100},
        {"label": _("库存匹数"), "fieldname": "stock_roll_count", "fieldtype": "Float", "precision": 2, "width": 110},
        {"label": _("库存数量"), "fieldname": "stock_qty", "fieldtype": "Float", "precision": 2, "width": 110},
        {"label": _("入库匹数"), "fieldname": "receipt_roll_count", "fieldtype": "Float", "precision": 2, "width": 110},
        {"label": _("入库数量"), "fieldname": "receipt_qty", "fieldtype": "Float", "precision": 2, "width": 110},
        {"label": _("出库匹数"), "fieldname": "issue_roll_count", "fieldtype": "Float", "precision": 2, "width": 110},
        {"label": _("出库数量"), "fieldname": "issue_qty", "fieldtype": "Float", "precision": 2, "width": 110},
        {"label": _("单位"), "fieldname": "stock_uom", "fieldtype": "Data", "width": 75},
        {"label": _("仓库"), "fieldname": "warehouse", "fieldtype": "Data", "width": 150},
        {"label": _("货位编号"), "fieldname": "location", "fieldtype": "Data", "width": 180},
        {"label": _("入库日期"), "fieldname": "receipt_date", "fieldtype": "Date", "width": 100},
        {"label": _("颜色"), "fieldname": "color", "fieldtype": "Data", "width": 100},
    ]
    data = frappe.db.sql("""
        SELECT sle.item_code, item.item_name,
            COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no) AS batch_no,
            COALESCE(MAX(transfer_source.customer_name), MAX(COALESCE(receipt.customer_name, receipt.customer))) AS customer_name,
            COALESCE(MAX(transfer_source.stock_source), '客户胚布入库') AS stock_source,
            MAX(transfer_source.production_flow_card) AS source_flow_card,
            MAX(transfer_source.source_transfer) AS source_transfer,
            MAX(transfer_source.source_batch_no) AS source_batch_no,
            COALESCE(MAX(receipt_item.color), MAX(transfer_source.color)) AS color,
            COALESCE(MAX(receipt_item.width), MAX(transfer_source.width)) AS width,
            COALESCE(MAX(receipt_item.gsm), MAX(transfer_source.gsm)) AS gsm,
            CASE
                WHEN stock_warehouse.parent_warehouse = '胚布货位 - 沅泰' THEN '胚布仓库 - 沅泰'
                ELSE sle.warehouse
            END AS warehouse,
            CASE
                WHEN stock_warehouse.parent_warehouse = '胚布货位 - 沅泰' THEN sle.warehouse
                ELSE NULL
            END AS location,
            CASE
                WHEN sle.warehouse = %(transit_warehouse)s THEN GREATEST(COALESCE(MAX(transfer_rolls.roll_delta), 0), 0)
                ELSE GREATEST(
                    COALESCE(MAX(receipt_rolls.stock_roll_count), 0)
                    + COALESCE(MAX(transfer_rolls.roll_delta), 0),
                    0
                )
            END AS stock_roll_count,
            SUM(sle.actual_qty) AS stock_qty,
            COALESCE(MAX(receipt_rolls.receipt_roll_count), MAX(transfer_source.receipt_roll_count), 0) AS receipt_roll_count,
            COALESCE(MAX(receipt_rolls.receipt_qty), MAX(transfer_source.receipt_qty), 0) AS receipt_qty,
            COALESCE(MAX(issued_rolls.issue_roll_count), 0) AS issue_roll_count,
            COALESCE(MAX(issued_rolls.issue_qty), 0) AS issue_qty,
            MAX(item.stock_uom) AS stock_uom,
            COALESCE(
                MAX(receipt.receipt_date),
                MAX(transfer_source.receipt_date),
                MAX(CASE WHEN sle.actual_qty > 0 THEN sle.posting_date END)
            ) AS receipt_date
        FROM `tabStock Ledger Entry` sle
        INNER JOIN `tabItem` item ON item.name = sle.item_code
        LEFT JOIN `tabWarehouse` stock_warehouse ON stock_warehouse.name = sle.warehouse
        LEFT JOIN `tabSerial and Batch Entry` bundle_entry ON bundle_entry.parent = sle.serial_and_batch_bundle
        LEFT JOIN `tabCustomer Grey Fabric Receipt Item` receipt_item
            ON receipt_item.batch_no = COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no)
        LEFT JOIN `tabCustomer Grey Fabric Receipt` receipt
            ON receipt.name = receipt_item.parent AND receipt.docstatus = 1
        LEFT JOIN (
            SELECT source.item_code, source.batch_no,
                MAX(source.customer_name) AS customer_name,
                MAX(source.production_flow_card) AS production_flow_card,
                MAX(source.source_transfer) AS source_transfer,
                MAX(source.source_batch_no) AS source_batch_no,
                MAX(source.stock_source) AS stock_source,
                MAX(source.receipt_date) AS receipt_date,
                MAX(source.receipt_roll_count) AS receipt_roll_count,
                MAX(source.receipt_qty) AS receipt_qty,
                MAX(source.color) AS color,
                MAX(source.width) AS width,
                MAX(source.gsm) AS gsm
            FROM (
                SELECT transfer.grey_fabric_item AS item_code, transfer.return_batch_no AS batch_no,
                    COALESCE(NULLIF(transfer.customer_name, ''), customer.customer_name, transfer.customer) AS customer_name,
                    transfer.production_flow_card, transfer.name AS source_transfer, NULL AS source_batch_no, '成品退货返修' AS stock_source,
                    transfer.transfer_date AS receipt_date, transfer.total_roll_count AS receipt_roll_count,
                    transfer.total_weight AS receipt_qty, card.color, card.finished_width AS width,
                    card.finished_gsm AS gsm
                FROM `tabFinished Product Return to Grey Fabric` transfer
                LEFT JOIN `tabCustomer` customer ON customer.name = transfer.customer
                LEFT JOIN `tabProduction Flow Card` card ON card.name = transfer.production_flow_card
                WHERE transfer.docstatus = 1 AND transfer.transfer_status = '已转胚布'
                UNION ALL
                SELECT transfer.grey_fabric_item AS item_code, transfer.return_batch_no AS batch_no,
                    COALESCE(NULLIF(transfer.customer_name, ''), customer.customer_name, transfer.customer) AS customer_name,
                    transfer.production_flow_card, transfer.name AS source_transfer, NULL AS source_batch_no, '厂内成品返修' AS stock_source,
                    transfer.transfer_date AS receipt_date, transfer.total_roll_count AS receipt_roll_count,
                    transfer.total_weight AS receipt_qty, card.color, card.finished_width AS width,
                    card.finished_gsm AS gsm
                FROM `tabFinished Product to Grey Fabric` transfer
                LEFT JOIN `tabCustomer` customer ON customer.name = transfer.customer
                LEFT JOIN `tabProduction Flow Card` card ON card.name = transfer.production_flow_card
                WHERE transfer.docstatus = 1 AND transfer.transfer_status = '已转胚布仓'
                UNION ALL
                SELECT detail.item_code, detail.target_batch_no AS batch_no,
                    COALESCE(NULLIF(transfer.target_customer_name, ''), customer.customer_name, transfer.target_customer) AS customer_name,
                    NULL AS production_flow_card, transfer.name AS source_transfer, detail.source_batch_no, '胚布过户' AS stock_source,
                    transfer.transfer_date AS receipt_date, detail.transfer_roll_count AS receipt_roll_count,
                    detail.transfer_qty AS receipt_qty, detail.color, source_item.width, source_item.gsm
                FROM `tabGrey Fabric Customer Transfer Item` detail
                INNER JOIN `tabGrey Fabric Customer Transfer` transfer
                    ON transfer.name = detail.parent AND transfer.docstatus = 1
                LEFT JOIN `tabCustomer` customer ON customer.name = transfer.target_customer
                LEFT JOIN `tabCustomer Grey Fabric Receipt Item` source_item
                    ON source_item.batch_no = detail.source_batch_no
                WHERE transfer.transfer_status = '已过户'
            ) source
            GROUP BY source.item_code, source.batch_no
        ) transfer_source ON transfer_source.item_code = sle.item_code
            AND transfer_source.batch_no = COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no)
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
          AND sle.warehouse != %(transit_warehouse)s
          AND item.item_group IN (
            SELECT name FROM `tabItem Group`
            WHERE lft >= (SELECT lft FROM `tabItem Group` WHERE name = %(grey_group)s)
              AND rgt <= (SELECT rgt FROM `tabItem Group` WHERE name = %(grey_group)s)
          )
        GROUP BY sle.item_code, item.item_name,
            COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no), sle.warehouse
        HAVING SUM(sle.actual_qty) > 0
        ORDER BY receipt_date DESC, batch_no DESC
    """, {"transit_warehouse": get_setting("production_transit_warehouse"), "grey_group": get_setting("grey_fabric_item_group")}, as_dict=True)
    return columns, data
