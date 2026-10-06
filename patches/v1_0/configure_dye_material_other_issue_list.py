import json

import frappe
from frappe.desk.doctype.list_view_settings.list_view_settings import set_listview_fields


DOCTYPE = "Dye Material Other Issue"
FIELDS = [
    {"label": "编号", "fieldname": "name"},
    {"label": "出库日期", "fieldname": "issue_date"},
    {"label": "物料名称", "fieldname": "item_names"},
    {"label": "本次出库克数", "fieldname": "total_issue_qty_g"},
    {"label": "本次出库公斤数", "fieldname": "total_issue_qty_kg"},
    {"label": "出库仓库", "fieldname": "source_warehouse"},
    {"label": "状态", "fieldname": "status_field"},
    {"label": "出库用途", "fieldname": "issue_purpose"},
    {"label": "生产流转卡", "fieldname": "production_flow_card"},
]


def execute():
    if not frappe.db.exists("DocType", DOCTYPE):
        return
    if frappe.db.exists("List View Settings", DOCTYPE):
        settings = frappe.get_doc("List View Settings", DOCTYPE)
    else:
        settings = frappe.new_doc("List View Settings")
        settings.name = DOCTYPE
    settings.fields = json.dumps(FIELDS, ensure_ascii=False)
    settings.save(ignore_permissions=True)

    meta = frappe.get_meta(DOCTYPE)
    visible = {field["fieldname"] for field in FIELDS}
    current = [field.fieldname for field in meta.fields if field.in_list_view]
    set_listview_fields(DOCTYPE, FIELDS, [field for field in current if field not in visible])
    frappe.clear_cache(doctype=DOCTYPE)
