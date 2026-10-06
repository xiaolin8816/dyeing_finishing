import frappe
from frappe import _


DYEING_WAREHOUSE = "染料仓库 - 沅泰"
DYEING_MATERIAL_GROUPS = ("染料", "助剂")
DYEING_RECEIPT_TYPE = "染料/助剂入库"


def execute(filters=None):
    filters = filters or {}
    columns = [
        {"label": _("物料编码"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
        {"label": _("物料名称"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": _("类别"), "fieldname": "material_category", "fieldtype": "Data", "width": 90},
        {"label": _("包装规格"), "fieldname": "packaging_specification", "fieldtype": "Data", "width": 130},
        {"label": _("仓库"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 170},
        {"label": _("库存数量"), "fieldname": "actual_qty", "fieldtype": "Float", "precision": 2, "width": 110},
        {"label": _("单位"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 80},
        {"label": _("库存金额"), "fieldname": "stock_value", "fieldtype": "Currency", "width": 120},
        {"label": _("最近入库日期"), "fieldname": "last_receipt_date", "fieldtype": "Date", "width": 110},
        {"label": _("供应商名称"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 170},
    ]

    conditions = ["warehouse.name = %(warehouse)s"]
    values = {"warehouse": filters.get("warehouse") or DYEING_WAREHOUSE, "groups": DYEING_MATERIAL_GROUPS}

    if not filters.get("include_zero_stock"):
        conditions.append("bin.actual_qty != 0")
    if filters.get("material_category"):
        conditions.append("material_group.name = %(material_category)s")
        values["material_category"] = filters.get("material_category")
    if filters.get("item_code"):
        conditions.append("bin.item_code = %(item_code)s")
        values["item_code"] = filters.get("item_code")

    data = frappe.db.sql(
        f"""
        SELECT
            bin.item_code,
            item.item_name,
            material_group.name AS material_category,
            item.custom_dyeing_packing_specification AS packaging_specification,
            bin.warehouse,
            bin.actual_qty,
            item.stock_uom,
            bin.stock_value,
            receipt.last_receipt_date,
            receipt.supplier_name
        FROM `tabBin` bin
        INNER JOIN `tabWarehouse` warehouse ON warehouse.name = bin.warehouse
        INNER JOIN `tabItem` item ON item.name = bin.item_code
        INNER JOIN `tabItem Group` item_group ON item_group.name = item.item_group
        INNER JOIN `tabItem Group` material_group
            ON material_group.name IN %(groups)s
            AND item_group.lft >= material_group.lft
            AND item_group.rgt <= material_group.rgt
        LEFT JOIN (
            SELECT
                receipt_item.item_code,
                receipt_item.warehouse,
                MAX(receipt.posting_date) AS last_receipt_date,
                SUBSTRING_INDEX(
                    GROUP_CONCAT(receipt.supplier_name ORDER BY receipt.posting_date DESC, receipt.modified DESC),
                    ',',
                    1
                ) AS supplier_name
            FROM `tabPurchase Receipt Item` receipt_item
            INNER JOIN `tabPurchase Receipt` receipt
                ON receipt.name = receipt_item.parent
                AND receipt.docstatus = 1
                AND receipt.custom_dyeing_receipt_type = %(receipt_type)s
            GROUP BY receipt_item.item_code, receipt_item.warehouse
        ) receipt
            ON receipt.item_code = bin.item_code
            AND receipt.warehouse = bin.warehouse
        WHERE {' AND '.join(conditions)}
        ORDER BY material_group.name, item.item_name, bin.item_code
        """,
        {**values, "receipt_type": DYEING_RECEIPT_TYPE},
        as_dict=True,
    )
    return columns, data
