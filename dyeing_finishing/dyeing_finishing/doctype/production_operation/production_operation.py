# Copyright (c) 2026, Xiaolin Hang and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import getseries


def _get_parent_code(parent_operation):
    parent_code = frappe.db.get_value(
        "Production Operation",
        parent_operation,
        "production_operation_code",
    )
    if not parent_code:
        frappe.throw("未找到上级生产工序编码")
    return str(parent_code).zfill(3)[:3]


def _preview_series_code(series_key, digits):
    current = frappe.db.sql(
        "SELECT current FROM `tabSeries` WHERE name=%s",
        (series_key,),
        as_list=True,
    )
    sequence = int(current[0][0] or 0) + 1 if current else 1
    return f"{sequence:0{digits}d}"


@frappe.whitelist()
def get_next_main_operation_code():
    return _preview_series_code("Production Operation Main-", 3)


@frappe.whitelist()
def get_next_child_operation_code(parent_operation):
    parent_code = _get_parent_code(parent_operation)
    sequence = _preview_series_code(f"Production Operation Child {parent_code}-", 3)
    return f"{parent_code}{sequence}"


class ProductionOperation(Document):
    def autoname(self):
        if self.parent_production_operation:
            parent_code = _get_parent_code(self.parent_production_operation)
            sequence = getseries(f"Production Operation Child {parent_code}-", 3)
            self.production_operation_code = f"{parent_code}{sequence}"
        else:
            self.production_operation_code = getseries("Production Operation Main-", 3)
        self.name = self.production_operation_code

    def validate(self):
        if not self.parent_production_operation:
            return

        parent = frappe.db.get_value(
            "Production Operation",
            self.parent_production_operation,
            ["production_operation_code", "production_operation_name"],
            as_dict=True,
        )
        if parent:
            self.sub_operation_code = parent.production_operation_code
            self.sub_operation_name = parent.production_operation_name
