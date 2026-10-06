import json
from pathlib import Path

import frappe


def execute():
    """按应用内定义的 field_order 统一生产流转卡字段顺序。"""
    doctype = "Production Flow Card"
    source_file = Path(
        frappe.get_app_path(
            "dyeing_finishing", "dyeing_finishing", "doctype",
            "production_flow_card", "production_flow_card.json",
        )
    )
    field_order = json.loads(source_file.read_text(encoding="utf-8"))["field_order"]
    for idx, fieldname in enumerate(field_order, start=1):
        frappe.db.set_value(
            "DocField",
            {"parent": doctype, "fieldname": fieldname},
            "idx",
            idx,
            update_modified=False,
        )
    frappe.clear_cache(doctype=doctype)
