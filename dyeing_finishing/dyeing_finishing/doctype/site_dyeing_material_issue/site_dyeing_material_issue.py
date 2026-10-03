import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt, getdate, nowdate

from dyeing_finishing.dyeing_finishing.doctype.production_flow_card.production_flow_card import (
    ensure_flow_card_open,
    record_production_progress,
)


DYE_WAREHOUSE = "染料仓库 - 沅泰"


class SiteDyeingMaterialIssue(Document):
    def autoname(self):
        self.name = make_autoname("CL.YY.MM.DD.###")
        self.document_code = self.name

    def before_insert(self):
        self.document_code = self.name
        self.issue_date = self.issue_date or getdate(nowdate())
        self.document_status = "保存"

    def validate(self):
        self.document_code = self.name
        self.issue_date = self.issue_date or getdate(nowdate())
        self._set_material_sheet_details()
        self._set_item_details()
        self._set_totals()

    def before_submit(self):
        if not self.items:
            frappe.throw(_("领料明细不能为空"))
        if not any(flt(row.issue_qty_g) > 0 for row in self.items):
            frappe.throw(_("请至少填写一行本次出库克数"))
        self.document_status = "已提交"

    def on_submit(self):
        self._create_stock_entry()
        self._refresh_material_sheet_issue_status()
        record_production_progress(
            self.production_flow_card,
            "染料领料",
            "已领料",
            "Site Dyeing Material Issue",
            self.name,
            quantity=self.total_issue_qty_kg,
            uom="kg",
            dyeing_machine=self.dyeing_machine,
            description=_("现场染色领料单：{0}；本次领料 {1} kg").format(self.name, self.total_issue_qty_kg),
        )

    def on_cancel(self):
        if self.stock_entry:
            entry = frappe.get_doc("Stock Entry", self.stock_entry)
            if entry.docstatus == 1:
                entry.cancel()
        self.db_set("stock_entry", None, update_modified=False)
        self.stock_entry = None
        self._refresh_material_sheet_issue_status()
        self.db_set("document_status", "已取消", update_modified=False)
        record_production_progress(
            self.production_flow_card,
            "染料领料",
            "领料已撤销",
            "Site Dyeing Material Issue",
            self.name,
            quantity=self.total_issue_qty_kg,
            uom="kg",
            dyeing_machine=self.dyeing_machine,
            description=_("现场染色领料单已撤销：{0}").format(self.name),
        )

    def _set_material_sheet_details(self):
        if not self.material_sheet:
            frappe.throw(_("请选择现场染色料单"))
        sheet = frappe.get_doc("Site Dyeing Material Sheet", self.material_sheet)
        if sheet.docstatus != 1 or sheet.material_sheet_status not in ("待领料", "部分领料"):
            frappe.throw(_("只能引用待领料或部分领料的已提交现场染色料单"))
        ensure_flow_card_open(frappe.get_doc("Production Flow Card", sheet.production_flow_card))
        self.production_flow_card = sheet.production_flow_card
        self.sales_order = sheet.sales_order
        self.customer_name = sheet.customer_name
        self.color_no = sheet.color_no
        self.color = sheet.color
        self.finished_product_name = sheet.finished_product_name
        self.dyeing_machine = sheet.dyeing_machine
        self.source_warehouse = self.source_warehouse or DYE_WAREHOUSE

    def _set_item_details(self):
        if not frappe.db.exists("Warehouse", self.source_warehouse):
            frappe.throw(_("未找到出库仓库：{0}").format(self.source_warehouse))
        sheet_items = {row.name: row for row in frappe.get_doc("Site Dyeing Material Sheet", self.material_sheet).items}
        totals_by_item = {}
        for row in self.items:
            source = sheet_items.get(row.material_sheet_item)
            if not source:
                frappe.throw(_("领料明细必须来自所选现场染色料单"))
            row.item_code = source.item_code
            row.item_name = source.item_name
            row.material_category = source.material_category
            row.planned_qty_g = flt(source.actual_qty)
            row.issued_qty_g = get_issued_qty(source.name, exclude_name=self.name)
            row.issue_status = _issue_status(row.planned_qty_g, row.issued_qty_g)
            row.issue_qty_g = flt(row.issue_qty_g)
            if row.issue_qty_g < 0 or row.issued_qty_g + row.issue_qty_g > row.planned_qty_g:
                frappe.throw(_("物料 {0} 的本次出库克数不能超过未领数量").format(row.item_name or row.item_code))
            row.issue_qty_kg = flt(row.issue_qty_g / 1000, 6)
            item = frappe.get_doc("Item", row.item_code)
            row.stock_uom = item.stock_uom
            row.stock_qty_kg = flt(frappe.db.get_value("Bin", {"item_code": row.item_code, "warehouse": self.source_warehouse}, "actual_qty") or 0)
            totals_by_item[row.item_code] = totals_by_item.get(row.item_code, 0) + row.issue_qty_kg
        for item_code, qty_kg in totals_by_item.items():
            available = flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": self.source_warehouse}, "actual_qty") or 0)
            if qty_kg > available:
                frappe.throw(_("物料 {0} 的库存不足，库存 {1} kg，本次需出库 {2} kg").format(item_code, available, qty_kg))

    def _set_totals(self):
        self.total_issue_qty_g = sum(flt(row.issue_qty_g) for row in self.items)
        self.total_issue_qty_kg = flt(self.total_issue_qty_g / 1000, 6)

    def _create_stock_entry(self):
        if self.stock_entry:
            return
        company = frappe.db.get_value("Warehouse", self.source_warehouse, "company")
        items = [{
            "item_code": row.item_code,
            "qty": row.issue_qty_kg,
            "uom": row.stock_uom,
            "s_warehouse": self.source_warehouse,
            "allow_zero_valuation_rate": 1,
            "custom_production_flow_card": self.production_flow_card,
            "custom_site_dyeing_material_issue": self.name,
            "custom_site_dyeing_material_sheet": self.material_sheet,
        } for row in self.items if flt(row.issue_qty_kg) > 0]
        entry = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Issue",
            "purpose": "Material Issue",
            "company": company,
            "posting_date": self.issue_date,
            "remarks": _("现场染色领料单：{0}；现场染色料单：{1}；生产流转卡：{2}").format(self.name, self.material_sheet, self.production_flow_card),
            "items": items,
        })
        entry.insert(ignore_permissions=True)
        entry.submit()
        self.db_set("stock_entry", entry.name, update_modified=False)
        self.stock_entry = entry.name

    def _refresh_material_sheet_issue_status(self):
        sheet = frappe.get_doc("Site Dyeing Material Sheet", self.material_sheet)
        for row in sheet.items:
            issued = get_issued_qty(row.name)
            status = _issue_status(row.actual_qty, issued)
            frappe.db.set_value("Site Dyeing Material Sheet Item", row.name, {"issued_qty": issued, "issue_status": status}, update_modified=False)
        rows = frappe.get_all("Site Dyeing Material Sheet Item", filters={"parent": sheet.name}, fields=["actual_qty", "issued_qty"])
        status = "已领料" if rows and all(flt(row.issued_qty) >= flt(row.actual_qty) for row in rows) else "部分领料" if any(flt(row.issued_qty) > 0 for row in rows) else "待领料"
        frappe.db.set_value("Site Dyeing Material Sheet", sheet.name, "material_sheet_status", status, update_modified=False)


def _issue_status(planned, issued):
    return "已领料" if flt(issued) >= flt(planned) and flt(planned) > 0 else "部分领料" if flt(issued) > 0 else "未领料"


def get_issued_qty(material_sheet_item, exclude_name=None):
    conditions = ["item.material_sheet_item = %(material_sheet_item)s", "parent.docstatus = 1"]
    values = {"material_sheet_item": material_sheet_item}
    if exclude_name:
        conditions.append("parent.name != %(exclude_name)s")
        values["exclude_name"] = exclude_name
    return flt(frappe.db.sql("SELECT COALESCE(SUM(item.issue_qty_g), 0) AS total FROM `tabSite Dyeing Material Issue Item` item INNER JOIN `tabSite Dyeing Material Issue` parent ON parent.name = item.parent WHERE " + " AND ".join(conditions), values, as_dict=True)[0].total)


@frappe.whitelist()
def get_material_sheet_details(material_sheet):
    sheet = frappe.get_doc("Site Dyeing Material Sheet", material_sheet)
    sheet.check_permission("read")
    if sheet.docstatus != 1:
        frappe.throw(_("现场染色料单必须已提交"))
    data = {field: sheet.get(field) for field in ("production_flow_card", "sales_order", "customer_name", "color_no", "color", "finished_product_name", "dyeing_machine")}
    data["source_warehouse"] = DYE_WAREHOUSE
    data["items"] = []
    for row in sheet.items:
        issued = get_issued_qty(row.name)
        remaining = max(flt(row.actual_qty) - issued, 0)
        if remaining <= 0:
            continue
        item = frappe.get_doc("Item", row.item_code)
        data["items"].append({"material_sheet_item": row.name, "item_code": row.item_code, "item_name": row.item_name, "material_category": row.material_category, "planned_qty_g": row.actual_qty, "issued_qty_g": issued, "issue_qty_g": remaining, "issue_qty_kg": flt(remaining / 1000, 6), "stock_qty_kg": flt(frappe.db.get_value("Bin", {"item_code": row.item_code, "warehouse": DYE_WAREHOUSE}, "actual_qty") or 0), "stock_uom": item.stock_uom, "issue_status": _issue_status(row.actual_qty, issued)})
    return data

@frappe.whitelist()
def get_preview_document_code(issue_date=None):
    """Return the next document code for display only; it does not reserve a series number."""
    date = getdate(issue_date or nowdate())
    series_key = f"CL{date.strftime('%y%m%d')}"
    current = frappe.db.get_value("Series", series_key, "current") or 0
    return f"{series_key}{int(current) + 1:03d}"
