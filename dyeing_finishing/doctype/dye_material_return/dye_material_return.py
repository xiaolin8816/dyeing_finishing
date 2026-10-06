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
        self.name = make_autoname("CLTH.YY.MM.DD.####")
        self.document_code = self.name

    def before_insert(self):
        self.return_date = self.return_date or getdate(nowdate())
        self.document_code = self.name
        self.source_warehouse = self.source_warehouse or DYE_WAREHOUSE

    def validate(self):
        self.return_date = self.return_date or getdate(nowdate())
        if not self.is_new():
            self.document_code = self.name
        self.source_warehouse = self.source_warehouse or DYE_WAREHOUSE
        self.return_item_source = self.return_item_source or "原入库单带出"
        self._set_purchase_receipt_details()
        self._set_item_details()
        self._set_totals()
        self._set_item_names()

    def before_submit(self):
        if not self.items:
            frappe.throw(_("退货明细不能为空"))
        if not any(flt(row.return_qty_kg) > 0 for row in self.items):
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

    def _set_purchase_receipt_details(self):
        if self.return_item_source == "原入库单带出":
            if not self.original_purchase_receipt:
                frappe.throw(_("请选择原染料入库单"))
            receipt = frappe.get_doc("Purchase Receipt", self.original_purchase_receipt)
            if receipt.docstatus != 1:
                frappe.throw(_("原染料入库单必须已提交"))
            self.supplier = receipt.supplier
            receipt_items = {row.name: row for row in receipt.items}
            for row in self.items:
                if not row.purchase_receipt_item:
                    frappe.throw(_("退货明细必须从原染料入库单带出"))
                source = receipt_items.get(row.purchase_receipt_item)
                if not source:
                    frappe.throw(_("原入库明细不属于所选染料入库单"))
                item = frappe.db.get_value("Item", source.item_code, ["item_group", "stock_uom"], as_dict=True)
                if not item or not _get_material_category(item.item_group):
                    frappe.throw(_("原染料入库单中只能选择染料或助剂明细"))
                row.item_code = source.item_code
                row.item_name = source.item_name
                row.material_category = _get_material_category(item.item_group)
                row.batch_no = source.batch_no
                row.stock_uom = source.stock_uom or item.stock_uom
            return

        if not self.supplier:
            frappe.throw(_("手动选择库存退货时，请填写供应商"))
        self.original_purchase_receipt = None
        for row in self.items:
            if not row.item_code:
                frappe.throw(_("请选择退货物料"))
            item = frappe.db.get_value("Item", row.item_code, ["item_name", "item_group", "stock_uom"], as_dict=True)
            if not item or not _get_material_category(item.item_group):
                frappe.throw(_("只能选择染料或助剂物料"))
            row.purchase_receipt_item = None
            row.item_name = item.item_name
            row.material_category = _get_material_category(item.item_group)
            row.stock_uom = item.stock_uom

    def _set_item_details(self):
        if not frappe.db.exists("Warehouse", self.source_warehouse):
            frappe.throw(_("未找到退货仓库：{0}").format(self.source_warehouse))
        totals_by_item = {}
        item_batch_keys = set()
        for row in self.items:
            key = (row.purchase_receipt_item, row.batch_no or "") if self.return_item_source == "原入库单带出" else (row.item_code, row.batch_no or "")
            if key in item_batch_keys:
                frappe.throw(_("同一物料或原入库明细不能重复添加"))
            item_batch_keys.add(key)
            row.stock_qty_kg = flt(frappe.db.get_value("Bin", {"item_code": row.item_code, "warehouse": self.source_warehouse}, "actual_qty") or 0)
            row.return_qty_kg = flt(row.return_qty_kg, 4)
            if row.return_qty_kg < 0:
                frappe.throw(_("物料 {0} 的退货数量不能小于 0").format(row.item_name or row.item_code))
            totals_by_item[row.item_code] = totals_by_item.get(row.item_code, 0) + row.return_qty_kg
        if self.source_type == "染料仓库存":
            for item_code, qty in totals_by_item.items():
                available = flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": self.source_warehouse}, "actual_qty") or 0)
                if qty > available:
                    frappe.throw(_("物料 {0} 库存不足，仓库库存 {1} kg，本次退货 {2} kg").format(item_code, available, qty))

    def _set_totals(self):
        self.total_return_qty_kg = flt(sum(flt(row.return_qty_kg) for row in self.items), 4)

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
                "custom_dyeing_return_business_type": "染料退货",
                "custom_dye_material_return": self.name,
                "custom_dyeing_return_supplier": self.supplier,
                "custom_dyeing_return_reason": self.return_reason,
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
            "custom_dyeing_return_business_type": "染料退货",
            "custom_dye_material_return": self.name,
            "custom_dyeing_return_supplier": self.supplier,
            "custom_dyeing_return_reason": self.return_reason,
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
        INNER JOIN `tabBin` bin
            ON bin.item_code = item.name
            AND bin.warehouse = %(warehouse)s
            AND bin.actual_qty > 0
        WHERE item.disabled = 0
          AND (item.name LIKE %(txt)s OR item.item_name LIKE %(txt)s)
        ORDER BY item.name
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "groups": DYE_MATERIAL_GROUPS,
            "warehouse": (filters or {}).get("source_warehouse") or DYE_WAREHOUSE,
            "txt": f"%{txt}%",
            "start": start,
            "page_len": page_len,
        },
    )


@frappe.whitelist()
def get_manual_return_item_details(item_code, source_warehouse=None):
    source_warehouse = source_warehouse or DYE_WAREHOUSE
    item = frappe.db.get_value("Item", item_code, ["item_name", "item_group", "stock_uom"], as_dict=True)
    if not item or not _get_material_category(item.item_group):
        frappe.throw(_("只能选择染料或助剂物料"))
    stock_qty_kg = flt(
        frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": source_warehouse}, "actual_qty") or 0
    )
    if stock_qty_kg <= 0:
        frappe.throw(_("该物料在退货仓库没有可用库存"))
    return {
        "item_name": item.item_name,
        "material_category": _get_material_category(item.item_group),
        "stock_uom": item.stock_uom,
        "stock_qty_kg": stock_qty_kg,
    }


@frappe.whitelist()
def get_purchase_receipt_return_details(purchase_receipt, source_warehouse=None):
    receipt = frappe.get_doc("Purchase Receipt", purchase_receipt)
    receipt.check_permission("read")
    if receipt.docstatus != 1:
        frappe.throw(_("原染料入库单必须已提交"))
    source_warehouse = source_warehouse or DYE_WAREHOUSE
    if not frappe.db.exists("Warehouse", source_warehouse):
        frappe.throw(_("未找到退货仓库：{0}").format(source_warehouse))
    data = {"supplier": receipt.supplier, "items": []}
    for source in receipt.items:
        item = frappe.db.get_value("Item", source.item_code, ["item_group", "stock_uom"], as_dict=True)
        if not item or not _get_material_category(item.item_group):
            continue
        stock_qty_kg = flt(
            frappe.db.get_value(
                "Bin", {"item_code": source.item_code, "warehouse": source_warehouse}, "actual_qty"
            )
            or 0
        )
        if stock_qty_kg <= 0:
            continue
        data["items"].append({
            "purchase_receipt_item": source.name,
            "item_code": source.item_code,
            "item_name": source.item_name,
            "material_category": _get_material_category(item.item_group),
            "batch_no": source.batch_no,
            "stock_uom": source.stock_uom or item.stock_uom,
            "stock_qty_kg": stock_qty_kg,
            "return_qty_kg": 0,
        })
    return data


@frappe.whitelist()
def get_preview_document_code(return_date=None):
    date = getdate(return_date or nowdate())
    series_key = f"CLTH{date.strftime('%y%m%d')}"
    quote = chr(96)
    query = "SELECT " + quote + "current" + quote + " FROM " + quote + "tabSeries" + quote + " WHERE name = %s"
    row = frappe.db.sql(query, series_key, as_dict=True)
    current = row[0].current if row else 0
    return f"{series_key}{int(current) + 1:04d}"
