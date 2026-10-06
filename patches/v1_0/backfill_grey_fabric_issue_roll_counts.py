"""补回历史胚布出库库存转移明细的匹数。"""

import frappe
from frappe.utils import flt


def execute():
    if not frappe.db.has_column("Stock Entry Detail", "custom_roll_count"):
        return

    issues = frappe.get_all(
        "Grey Fabric Issue",
        filters={"docstatus": 1, "stock_entry": ["!=", ""]},
        fields=["name", "stock_entry", "flow_card"],
    )
    for issue in issues:
        issue_items = frappe.get_all(
            "Grey Fabric Issue Item",
            filters={"parent": issue.name, "docstatus": 1, "issue_qty": ["!=", 0]},
            fields=["issue_roll_count"],
            order_by="idx",
        )
        stock_items = frappe.get_all(
            "Stock Entry Detail",
            filters={"parent": issue.stock_entry, "docstatus": 1},
            fields=["name"],
            order_by="idx",
        )
        for issue_item, stock_item in zip(issue_items, stock_items):
            frappe.db.set_value(
                "Stock Entry Detail",
                stock_item.name,
                {
                    "custom_roll_count": flt(issue_item.issue_roll_count),
                    "custom_grey_fabric_issue": issue.name,
                    "custom_production_flow_card": issue.flow_card,
                },
                update_modified=False,
            )
