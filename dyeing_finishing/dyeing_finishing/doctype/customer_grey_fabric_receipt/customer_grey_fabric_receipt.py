# Copyright (c) 2026, Xiaolin Hang and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import getseries
from frappe.utils import flt, getdate


class CustomerGreyFabricReceipt(Document):
    def validate(self):
        if not self.items:
            frappe.throw(_("请至少填写一条胚布明细"))

        for row in self.items:
            if flt(row.weight_qty) <= 0:
                frappe.throw(_("第 {0} 行的重量必须大于 0").format(row.idx))

    def before_submit(self):
        self.create_automatic_batches()

    def create_automatic_batches(self):
        date_prefix = getdate(self.receipt_date).strftime("A%y%m%d")

        for row in self.items:
            if row.batch_no:
                continue

            # 客户胚布入库使用批次管理；第一次入库时自动为该物料启用。
            if not frappe.db.get_value("Item", row.item_code, "has_batch_no"):
                frappe.db.set_value("Item", row.item_code, "has_batch_no", 1, update_modified=False)

            batch_id = f"{date_prefix}{getseries(date_prefix, 3)}"
            while frappe.db.exists("Batch", batch_id):
                batch_id = f"{date_prefix}{getseries(date_prefix, 3)}"

            batch = frappe.get_doc(
                {
                    "doctype": "Batch",
                    "batch_id": batch_id,
                    "item": row.item_code,
                    "manufacturing_date": self.receipt_date,
                    "description": _("客户胚布入库单：{0}").format(self.name),
                }
            )
            batch.insert(ignore_permissions=True)
            row.batch_no = batch.name

    def on_submit(self):
        if self.stock_entry:
            return

        company = frappe.db.get_value("Warehouse", self.target_warehouse, "company")
        if not company:
            frappe.throw(_("入库仓库未设置公司"))

        stock_items = []
        for row in self.items:
            stock_item = {
                "item_code": row.item_code,
                "qty": flt(row.weight_qty),
                "uom": row.uom,
                "t_warehouse": row.target_location or self.target_warehouse,
                "allow_zero_valuation_rate": 1,
            }
            if row.batch_no:
                stock_item["batch_no"] = row.batch_no
            if row.barcode:
                stock_item["barcode"] = row.barcode
            stock_items.append(stock_item)

        stock_entry = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "purpose": "Material Receipt",
                "company": company,
                "posting_date": self.receipt_date,
                "to_warehouse": self.target_warehouse,
                "remarks": _("客户胚布入库：{0}；客户：{1}").format(self.name, self.customer),
                "items": stock_items,
            }
        )
        stock_entry.insert(ignore_permissions=True)
        stock_entry.submit()
        self.db_set("stock_entry", stock_entry.name, update_modified=False)

    def on_cancel(self):
        if not self.stock_entry:
            return

        stock_entry = frappe.get_doc("Stock Entry", self.stock_entry)
        if stock_entry.docstatus == 1:
            stock_entry.cancel()