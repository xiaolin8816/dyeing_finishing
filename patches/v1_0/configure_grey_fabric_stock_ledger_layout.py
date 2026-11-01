import frappe

from dyeing_finishing.dyeing_finishing.report.stock_report_column_widths import REPORT_CONFIGS


REPORT_NAME = "Grey Fabric Stock Ledger"
VISIBLE_FIELDS = [
    "posting_date",
    "business_type",
    "business_document",
    "customer_name",
    "batch_no",
    "item_name",
    "warehouse",
    "counterparty_warehouse",
    "receipt_roll_count",
    "issue_roll_count",
    "balance_roll_count",
    "receipt_qty",
    "issue_qty",
    "balance_qty",
]
WIDTHS = {
    "posting_date": 105,
    "business_type": 130,
    "business_document": 155,
    "customer_name": 150,
    "batch_no": 145,
    "item_name": 175,
    "warehouse": 165,
    "counterparty_warehouse": 165,
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
        "sticky": ["posting_date", "business_document", "batch_no"],
    }
    frappe.db.set_global(config["key"], frappe.as_json(layout))
    frappe.db.delete("DefaultValue", {"defkey": config["user_key"]})
    frappe.clear_cache()
