import frappe

from dyeing_finishing.dyeing_finishing.report.stock_report_column_widths import REPORT_CONFIGS


REPORT_NAME = "Grey Fabric Stock Ledger"
VISIBLE_FIELDS = [
    "customer_name",
    "item_name",
    "batch_no",
    "warehouse",
    "posting_date",
    "business_type",
    "business_document",
    "counterparty_warehouse",
    "receipt_roll_count",
    "issue_roll_count",
    "balance_roll_count",
    "receipt_qty",
    "issue_qty",
    "balance_qty",
]
WIDTHS = {
    "customer_name": 130,
    "item_name": 160,
    "batch_no": 140,
    "warehouse": 150,
    "posting_date": 105,
    "business_type": 130,
    "business_document": 155,
    "counterparty_warehouse": 150,
    "receipt_roll_count": 90,
    "issue_roll_count": 90,
    "balance_roll_count": 105,
    "receipt_qty": 120,
    "issue_qty": 120,
    "balance_qty": 135,
}


def execute():
    config = REPORT_CONFIGS[REPORT_NAME]
    layout = {
        "widths": WIDTHS,
        "order": VISIBLE_FIELDS,
        "hidden": sorted(config["fields"] - set(VISIBLE_FIELDS)),
        "sticky": VISIBLE_FIELDS[:4],
    }
    frappe.db.set_global(config["key"], frappe.as_json(layout))
    frappe.db.delete("DefaultValue", {"defkey": config["user_key"]})
    frappe.clear_cache()
