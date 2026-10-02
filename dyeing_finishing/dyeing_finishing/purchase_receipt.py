import frappe
from frappe import _
from frappe.model.naming import make_autoname
from frappe.utils import getdate, nowdate

DYEING_RECEIPT_TYPE = "染料/助剂入库"
DYEING_MATERIAL_GROUPS = ("染料", "助剂")
DYEING_WAREHOUSE = "染料仓库 - 沅泰"


def _get_dyeing_material_category(item_code):
    item_group = frappe.db.get_value("Item", item_code, "item_group")
    if not item_group:
        return ""
    category = frappe.db.sql(
        """
        SELECT root.name
        FROM `tabItem Group` item_group
        INNER JOIN `tabItem Group` root
            ON root.name IN %(groups)s
            AND item_group.lft >= root.lft
            AND item_group.rgt <= root.rgt
        WHERE item_group.name = %(item_group)s
        LIMIT 1
        """,
        {"groups": DYEING_MATERIAL_GROUPS, "item_group": item_group},
    )
    return category[0][0] if category else ""


def autoname(doc, method=None):
    if doc.get("custom_dyeing_receipt_type") != DYEING_RECEIPT_TYPE:
        return

    receipt_date = getdate(doc.get("posting_date") or nowdate())
    doc.name = make_autoname(f"PR{receipt_date:%y%m%d}.####")


def validate(doc, method=None):
    if doc.get("custom_dyeing_receipt_type") != DYEING_RECEIPT_TYPE:
        return
    doc.set_warehouse = doc.set_warehouse or DYEING_WAREHOUSE
    for row in doc.get("items") or []:
        category = _get_dyeing_material_category(row.item_code)
        if not category:
            frappe.throw(_("第 {0} 行物料只能选择物料组为染料或助剂的物料").format(row.idx))
        row.custom_dyeing_material_category = category
        row.custom_dyeing_packaging_specification = (
            frappe.db.get_value("Item", row.item_code, "custom_dyeing_packing_specification") or ""
        )
        row.warehouse = row.warehouse or DYEING_WAREHOUSE


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_dyeing_material_items(doctype, txt, searchfield, start, page_len, filters=None):
    return frappe.db.sql(
        """
        SELECT item.name, item.item_name, root.name AS material_category
        FROM `tabItem` item
        INNER JOIN `tabItem Group` item_group ON item_group.name = item.item_group
        INNER JOIN `tabItem Group` root
            ON root.name IN %(groups)s
            AND item_group.lft >= root.lft
            AND item_group.rgt <= root.rgt
        WHERE item.disabled = 0
          AND (item.name LIKE %(txt)s OR item.item_name LIKE %(txt)s)
        ORDER BY root.name, item.name
        LIMIT %(page_len)s OFFSET %(start)s
        """,
        {
            "groups": DYEING_MATERIAL_GROUPS,
            "txt": f"%{txt}%",
            "page_len": page_len,
            "start": start,
        },
    )
