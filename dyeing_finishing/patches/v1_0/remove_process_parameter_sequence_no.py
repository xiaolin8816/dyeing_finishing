"""删除工艺参数模板和化验室配方子表中重复的顺序号列。"""

import frappe


def execute():
    for doctype in (
        "Process Parameter Template Item",
        "Laboratory Recipe Process Parameter",
    ):
        if frappe.db.has_column(doctype, "sequence_no"):
            frappe.db.sql(
                f"ALTER TABLE `tab{doctype}` DROP COLUMN `sequence_no`"
            )
