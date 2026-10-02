import json
from pathlib import Path

import frappe


def execute():
    module_path = Path(frappe.get_module_path("dyeing_finishing.dyeing_finishing"))
    doctype_json = module_path / "doctype" / "production_flow_card" / "production_flow_card.json"
    with doctype_json.open(encoding="utf-8") as source:
        field_order = json.load(source)["field_order"]

    for index, fieldname in enumerate(field_order, start=1):
        frappe.db.sql(
            "UPDATE " + chr(96) + "tabDocField" + chr(96)
            + " SET idx=%s WHERE parent='Production Flow Card' AND fieldname=%s",
            (index, fieldname),
        )

    frappe.clear_cache(doctype="Production Flow Card")
