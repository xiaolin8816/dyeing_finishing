import frappe
from frappe import _


TARGET_WAREHOUSE = "生产中转仓 - 沅泰"


def execute(filters=None):
    columns = [
        {"label": _("客户"), "fieldname": "customer_name", "fieldtype": "Data", "width": 170},
        {"label": _("批次"), "fieldname": "batch_no", "fieldtype": "Data", "width": 145},
        {"label": _("胚布名称"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": _("库存匹数"), "fieldname": "stock_roll_count", "fieldtype": "Float", "precision": 2, "width": 110},
        {"label": _("库存数量"), "fieldname": "stock_qty", "fieldtype": "Float", "precision": 2, "width": 110},
        {"label": _("单位"), "fieldname": "stock_uom", "fieldtype": "Data", "width": 75},
        {"label": _("胚布出库单"), "fieldname": "grey_fabric_issue", "fieldtype": "Data", "width": 150},
        {"label": _("生产流转卡"), "fieldname": "production_flow_card", "fieldtype": "Data", "width": 150},
        {"label": _("仓库"), "fieldname": "warehouse", "fieldtype": "Data", "width": 160},
        {"label": _("入中转日期"), "fieldname": "transit_date", "fieldtype": "Date", "width": 110},
        {"label": _("颜色"), "fieldname": "color", "fieldtype": "Data", "width": 100},
    ]
    data = frappe.db.sql(
        """
        SELECT
            MAX(issue.customer_name) AS customer_name,
            COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no) AS batch_no,
            item.item_name, MAX(receipt_item.color) AS color,
            GREATEST(SUM(CASE
                WHEN sle.actual_qty > 0 THEN COALESCE(detail.custom_roll_count, 0)
                ELSE -COALESCE(detail.custom_roll_count, 0)
            END), 0) AS stock_roll_count,
            SUM(sle.actual_qty) AS stock_qty, MAX(item.stock_uom) AS stock_uom,
            detail.custom_grey_fabric_issue AS grey_fabric_issue,
            detail.custom_production_flow_card AS production_flow_card,
            sle.warehouse, MIN(sle.posting_date) AS transit_date
        FROM `tabStock Ledger Entry` sle
        INNER JOIN `tabItem` item ON item.name = sle.item_code
        LEFT JOIN `tabStock Entry Detail` detail ON detail.name = sle.voucher_detail_no
        LEFT JOIN `tabGrey Fabric Issue` issue
            ON issue.name = detail.custom_grey_fabric_issue AND issue.docstatus = 1
        LEFT JOIN `tabSerial and Batch Entry` bundle_entry ON bundle_entry.parent = sle.serial_and_batch_bundle
        LEFT JOIN `tabCustomer Grey Fabric Receipt Item` receipt_item
            ON receipt_item.batch_no = COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no)
        WHERE sle.is_cancelled = 0
          AND sle.warehouse = %(warehouse)s
          AND COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no) IS NOT NULL
          AND COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no) != ''
          AND item.item_group IN (
            SELECT name FROM `tabItem Group`
            WHERE lft >= (SELECT lft FROM `tabItem Group` WHERE name = '胚布')
              AND rgt <= (SELECT rgt FROM `tabItem Group` WHERE name = '胚布')
          )
        GROUP BY detail.custom_grey_fabric_issue, detail.custom_production_flow_card,
            sle.item_code, item.item_name, COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no), sle.warehouse
        HAVING SUM(sle.actual_qty) > 0
        ORDER BY transit_date DESC, batch_no DESC
        """,
        {"warehouse": TARGET_WAREHOUSE},
        as_dict=True,
    )
    return columns, data
