import frappe


def execute():
    """回修原因由成品退货单作为唯一业务来源，流转卡不再重复保存。"""
    frappe.db.delete(
        "DocField",
        {"parent": "Production Flow Card", "fieldname": "rework_reason"},
    )
    if frappe.db.has_column("Production Flow Card", "rework_reason"):
        frappe.db.sql_ddl(
            "ALTER TABLE `tabProduction Flow Card` DROP COLUMN `rework_reason`"
        )
    frappe.clear_cache(doctype="Production Flow Card")
