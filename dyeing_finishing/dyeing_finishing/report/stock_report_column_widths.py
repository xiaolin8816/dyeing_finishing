import frappe
from frappe import _
from frappe.utils import flt


MIN_WIDTH = 20
MAX_WIDTH = 600
REPORT_CONFIGS = {
    "Grey Fabric Stock": {
        "key": "grey_fabric_stock_report_column_widths",
        "fields": {
            "customer", "batch_no", "item_name", "color", "stock_roll_count",
            "stock_qty", "receipt_roll_count", "receipt_qty", "issue_roll_count",
            "issue_qty", "stock_uom", "location", "warehouse", "receipt_date",
        },
    },
    "Production Transit Warehouse Stock": {
        "key": "production_transit_warehouse_stock_report_column_widths",
        "fields": {
            "customer_name", "batch_no", "item_name", "color", "stock_roll_count",
            "stock_qty", "stock_uom", "grey_fabric_issue", "production_flow_card",
            "warehouse", "transit_date",
        },
    },
}


def _get_config(report_name):
    config = REPORT_CONFIGS.get(report_name)
    if not config:
        frappe.throw(_("不支持该报表的列宽设置"))
    return config


@frappe.whitelist()
def get_stock_report_column_widths(report_name):
    config = _get_config(report_name)
    return frappe.parse_json(frappe.db.get_global(config["key"]) or "{}")


@frappe.whitelist()
def set_stock_report_column_widths(report_name, widths):
    frappe.only_for("System Manager")
    config = _get_config(report_name)
    widths = frappe.parse_json(widths) or {}
    cleaned_widths = {}
    for fieldname, width in widths.items():
        width = flt(width)
        if fieldname not in config["fields"] or not width:
            continue
        if not MIN_WIDTH <= width <= MAX_WIDTH:
            frappe.throw(_("列宽应在 {0} 至 {1} 之间").format(MIN_WIDTH, MAX_WIDTH))
        cleaned_widths[fieldname] = int(width)
    frappe.db.set_global(config["key"], frappe.as_json(cleaned_widths))
    return cleaned_widths
