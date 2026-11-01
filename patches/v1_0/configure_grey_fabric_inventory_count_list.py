import json

import frappe
from frappe.desk.doctype.list_view_settings.list_view_settings import set_listview_fields


DOCTYPE = "Grey Fabric Inventory Count"
FIELDS = [
    {"label": "编号", "fieldname": "name"},
    {"label": "状态", "fieldname": "status_field"},
    {"label": "客户名称", "fieldname": "customer_name"},
    {"label": "批次", "fieldname": "batch_summary"},
    {"label": "胚布名称", "fieldname": "item_name_summary"},
    {"label": "账面匹数", "fieldname": "total_system_roll_count"},
    {"label": "实盘匹数", "fieldname": "total_actual_roll_count"},
    {"label": "账面重量", "fieldname": "total_system_qty"},
    {"label": "实盘重量", "fieldname": "total_actual_qty"},
    {"label": "差异匹数", "fieldname": "total_difference_roll_count"},
    {"label": "差异重量", "fieldname": "total_difference_qty"},
    {"label": "差异原因", "fieldname": "difference_reason_summary"},
    {"label": "盘点日期", "fieldname": "count_date"},
    {"label": "仓库", "fieldname": "warehouse"},
]
LAYOUT = {
    "widths": {
        "name": 125,
        "__status": 80,
        "customer_name": 120,
        "batch_summary": 145,
        "item_name_summary": 145,
        "total_system_roll_count": 85,
        "total_actual_roll_count": 85,
        "total_system_qty": 90,
        "total_actual_qty": 90,
        "total_difference_roll_count": 85,
        "total_difference_qty": 90,
        "difference_reason_summary": 115,
        "count_date": 100,
        "warehouse": 165,
    },
    "order": [
        "name", "__status", "customer_name", "batch_summary", "item_name_summary",
        "total_system_roll_count", "total_actual_roll_count", "total_system_qty", "total_actual_qty",
        "total_difference_roll_count", "total_difference_qty", "difference_reason_summary",
        "count_date", "warehouse",
    ],
    "hidden": [],
    "sticky": ["name", "__status"],
}


def execute():
    if not frappe.db.exists("DocType", DOCTYPE):
        return

    settings = (
        frappe.get_doc("List View Settings", DOCTYPE)
        if frappe.db.exists("List View Settings", DOCTYPE)
        else frappe.new_doc("List View Settings")
    )
    settings.name = DOCTYPE
    settings.fields = json.dumps(FIELDS, ensure_ascii=False)
    settings.disable_scrolling = 0
    settings.save(ignore_permissions=True)

    meta = frappe.get_meta(DOCTYPE)
    visible = {field["fieldname"] for field in FIELDS}
    current = [field.fieldname for field in meta.fields if field.in_list_view]
    set_listview_fields(DOCTYPE, FIELDS, [field for field in current if field not in visible])
    frappe.db.set_global("grey_fabric_inventory_count_list_layout", frappe.as_json(LAYOUT))

    for name in frappe.get_all(DOCTYPE, pluck="name"):
        doc = frappe.get_doc(DOCTYPE, name)
        doc._set_list_summaries()
        frappe.db.set_value(
            DOCTYPE,
            name,
            {
                "customer_name": doc.customer_name,
                "batch_summary": doc.batch_summary,
                "item_name_summary": doc.item_name_summary,
                "difference_reason_summary": doc.difference_reason_summary,
            },
            update_modified=False,
        )

    frappe.clear_cache(doctype=DOCTYPE)
