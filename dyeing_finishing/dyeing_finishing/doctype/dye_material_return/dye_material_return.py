import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt, getdate, nowdate

from dyeing_finishing.dyeing_finishing.doctype.dye_material_other_issue.dye_material_other_issue import (
    DYE_MATERIAL_GROUPS,
    _get_material_category,
    get_dye_material_item_details,
)

DYE_WAREHOUSE = "染料仓库 - 沅泰"


class DyeMaterialReturn(Document):
    def autoname(self):
        self.name = make_autoname("CLTH.YY.MM.DD.###")

    def before_insert(self):
        self.return_date = self.return_date or getdate(nowdate())
        self.source_warehouse = self.source_warehouse or DYE_WAREHOUSE

    def validate(self):
        self.return_date = self.return_date or getdate(nowdate())
        self.source_warehouse = self.source_warehouse or DYE_WAREHOUSE
        self._set_item_details()
        self._set_totals()
        self._set_item_names()

    def before_submit(self):
        if not self.items:
            frappe.throw(_("退货明细不能为空"))
        if not any(flt(row.return_qty_g) > 0 for row in self.items):
            frappe.throw(_("请至少填写一行退货数量"))

    def on_submit(self):
        self._create_stock_entries()

    def on_cancel(self):
        # Cancel the supplier-return issue first, then the automatic site return.
        for field in ("stock_entry", "material_receipt_entry"):
            entry_name = self.get(field)
            if not entry_name:
                continue
            entry = frappe.get_doc("Stock Entry", entry_name)
            if entry.docstatus == 1:
                entry.cancel()
            self.db_set(field, None, update_modified=False)
            self.set(field, None)

    def _set_item_details(self):
        if not frappe.db.exists("Warehouse", self.source_warehouse):
            frappe.throw(_("未找到退货仓库：{0}").format(self.source_warehouse))
        totals_by_item = {}
        item_batch_keys = set()
        for row in self.items:
            key = (row.item_code, row.batch_no or "")
            if key in item_batch_keys:
                frappe.throw(_("物料与批次不能重复添加"))
            item_batch_keys.add(key)
            details = get_dye_material_item_details(row.item_code, self.source_warehouse)
            row.item_name = details["item_name"]
            row.material_category = details["material_category"]
            row.stock_uom = details["stock_uom"]
            row.stock_qty_kg = details["stock_qty_kg"]
            row.return_qty_g = flt(row.return_qty_g)
            if row.return_qty_g <= 0:
                frappe.throw(_("物料 {0} 的退货数量必须大于 0").format(row.item_name or row.item_code))
            row.return_qty_kg = flt(row.return_qty_g / 1000, 6)
            totals_by_item[row.item_code] = totals_by_item.get(row.item_code, 0) + row.return_qty_kg
        if self.source_type == "染料仓库存":
            for item_code, qty in totals_by_item.items():
                available = flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": self.source_warehouse}, "actual_qty") or 0)
                if qty > available:
                    frappe.throw(_("物料 {0} 库存不足，仓库库存 {1} kg，本次退货 {2} kg").format(item_code, available, qty))

    def _set_totals(self):
        self.total_return_qty_g = sum(flt(row.return_qty_g) for row in self.items)
        self.total_return_qty_kg = flt(self.total_return_qty_g / 1000, 6)

    def _set_item_names(self):
        names = []
        for row in self.items:
            name = (row.item_name or row.item_code or "").strip()
            if name and name not in names:
                names.append(name)
        self.item_names = "、".join(names)

    def _entry_items(self, warehouse_field):
        rows = []
        for row in self.items:
            item = {
                "item_code": row.item_code,
                "qty": row.return_qty_kg,
                "uom": row.stock_uom,
                warehouse_field: self.source_warehouse,
                "allow_zero_valuation_rate": 1,
            }
            if row.batch_no:
                item["batch_no"] = row.batch_no
            rows.append(item)
        return rows

    def _create_stock_entries(self):
        company = frappe.db.get_value("Warehouse", self.source_warehouse, "company")
        if not company:
            frappe.throw(_("退货仓库未设置所属公司"))

        if self.source_type == "现场已领用" and not self.material_receipt_entry:
            receipt = frappe.get_doc({
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Receipt",
                "purpose": "Material Receipt",
                "company": company,
                "posting_date": self.return_date,
                "remarks": _("染料退货单现场自动回转：{0}").format(self.name),
                "items": self._entry_items("t_warehouse"),
            })
            receipt.insert(ignore_permissions=True)
            receipt.submit()
            self.db_set("material_receipt_entry", receipt.name, update_modified=False)
            self.material_receipt_entry = receipt.name

        if self.stock_entry:
            return
        issue = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Issue",
            "purpose": "Material Issue",
            "company": company,
            "posting_date": self.return_date,
            "remarks": _("染料退货单：{0}；供应商：{1}；原因：{2}").format(self.name, self.supplier, self.return_reason),
            "items": self._entry_items("s_warehouse"),
        })
        issue.insert(ignore_permissions=True)
        issue.submit()
        self.db_set("stock_entry", issue.name, update_modified=False)
        self.stock_entry = issue.name


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_dye_material_return_items(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql(
        """
        SELECT item.name, item.item_name
        FROM `tabItem` item
        INNER JOIN `tabItem Group` item_group ON item_group.name = item.item_group
        INNER JOIN `tabItem Group` material_group
            ON material_group.name IN %(groups)s
            AND item_group.lft >= material_group.lft
            AND item_group.rgt <= material_group.rgt
        WHERE item.disabled = 0
          AND (item.name LIKE %(txt)s OR item.item_name LIKE %(txt)s)
        ORDER BY item.name
        LIMIT %(start)s, %(page_len)s
        """,
        {"groups": DYE_MATERIAL_GROUPS, "txt": f"%{txt}%", "start": start, "page_len": page_len},
    )