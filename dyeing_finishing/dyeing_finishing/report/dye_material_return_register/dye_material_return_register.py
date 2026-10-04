import frappe
from frappe import _


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = [
        {"label": _("退货单号"), "fieldname": "dye_material_return", "fieldtype": "Link", "options": "Dye Material Return", "width": 145},
        {"label": _("退货日期"), "fieldname": "return_date", "fieldtype": "Date", "width": 100},
        {"label": _("供应商"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 160},
        {"label": _("物料编码"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 125},
        {"label": _("物料名称"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": _("退货数量(kg)"), "fieldname": "return_qty_kg", "fieldtype": "Float", "precision": 4, "width": 120},
        {"label": _("退货仓库"), "fieldname": "source_warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 160},
        {"label": _("退货原因"), "fieldname": "return_reason", "fieldtype": "Data", "width": 110},
        {"label": _("库存来源"), "fieldname": "source_type", "fieldtype": "Data", "width": 110},
        {"label": _("退货库存凭证"), "fieldname": "stock_entry", "fieldtype": "Link", "options": "Stock Entry", "width": 145},
        {"label": _("现场回转凭证"), "fieldname": "material_receipt_entry", "fieldtype": "Link", "options": "Stock Entry", "width": 145},
        {"label": _("状态"), "fieldname": "status", "fieldtype": "Data", "width": 90},
    ]

    conditions = ["return_doc.docstatus != 2", "return_item.return_qty_kg > 0"]
    values = {}
    for fieldname, column in (("from_date", "return_date >="), ("to_date", "return_date <=")):
        if filters.get(fieldname):
            conditions.append(f"return_doc.{column} %({fieldname})s")
            values[fieldname] = filters[fieldname]
    for fieldname in ("supplier", "source_warehouse", "return_reason"):
        if filters.get(fieldname):
            conditions.append(f"return_doc.{fieldname} = %({fieldname})s")
            values[fieldname] = filters[fieldname]
    if filters.get("status") == "已提交":
        conditions.append("return_doc.docstatus = 1")
    elif filters.get("status") == "保存":
        conditions.append("return_doc.docstatus = 0")

    data = frappe.db.sql(
        f"""
        SELECT
            return_doc.name AS dye_material_return,
            return_doc.return_date,
            return_doc.supplier,
            return_item.item_code,
            return_item.item_name,
            return_item.return_qty_kg,
            return_doc.source_warehouse,
            return_doc.return_reason,
            return_doc.source_type,
            return_doc.stock_entry,
            return_doc.material_receipt_entry,
            CASE return_doc.docstatus
                WHEN 0 THEN '保存'
                WHEN 1 THEN '已提交'
                WHEN 2 THEN '已取消'
            END AS status
        FROM `tabDye Material Return` return_doc
        INNER JOIN `tabDye Material Return Item` return_item ON return_item.parent = return_doc.name
        WHERE {' AND '.join(conditions)}
        ORDER BY return_doc.return_date DESC, return_doc.creation DESC, return_item.idx
        """,
        values,
        as_dict=True,
    )
    return columns, data
