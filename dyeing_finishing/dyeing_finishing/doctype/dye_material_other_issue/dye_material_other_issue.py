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
DYE_MATERIAL_GROUPS = ("染料", "助剂")


class DyeMaterialOtherIssue(Document):
    def autoname(self):
        self.name = make_autoname("CLQT.YY.MM.DD.###")

    def before_insert(self):
        self.issue_date = self.issue_date or getdate(nowdate())

    def validate(self):
        self.issue_date = self.issue_date or getdate(nowdate())
        self._set_item_details()
        self._set_totals()
        self._set_item_names()

    def before_submit(self):
        if not self.items:
            frappe.throw(_("出库明细不能为空"))
        if not any(flt(row.issue_qty_g) > 0 for row in self.items):
            frappe.throw(_("请至少填写一行出库数量"))
        if self.production_flow_card:
            ensure_flow_card_open(frappe.get_doc("Production Flow Card", self.production_flow_card))

    def on_submit(self):
        self._create_stock_entry()
        if self.production_flow_card:
            record_production_progress(
                self.production_flow_card,
                "其他染料出库",
                "已出库",
                "Dye Material Other Issue",
                self.name,
                quantity=self.total_issue_qty_kg,
                uom="kg",
                description=_("染料其他出库单：{0}；用途：{1}；本次出库 {2} kg").format(
                    self.name, self.issue_purpose, self.total_issue_qty_kg
                ),
            )

    def on_cancel(self):
        if self.stock_entry:
            entry = frappe.get_doc("Stock Entry", self.stock_entry)
            if entry.docstatus == 1:
                entry.cancel()
            # The cancelled stock entry is retained for audit, but must no longer
            # block cancellation of this source document through a reverse Link field.
            frappe.db.set_value(
                "Stock Entry Detail",
                {"parent": entry.name},
                "custom_dye_material_other_issue",
                None,
                update_modified=False,
            )
        self.db_set("stock_entry", None, update_modified=False)
        self.stock_entry = None
        if self.production_flow_card:
            record_production_progress(
                self.production_flow_card,
                "其他染料出库",
                "出库已撤销",
                "Dye Material Other Issue",
                self.name,
                quantity=self.total_issue_qty_kg,
                uom="kg",
                description=_("染料其他出库单已撤销：{0}").format(self.name),
            )

    def _set_item_details(self):
        if not frappe.db.exists("Warehouse", self.source_warehouse):
            frappe.throw(_("未找到出库仓库：{0}").format(self.source_warehouse))
        totals_by_item = {}
        item_codes = set()
        for row in self.items:
            if row.item_code in item_codes:
                frappe.throw(_("物料 {0} 不能重复添加").format(row.item_code))
            item_codes.add(row.item_code)
            details = get_dye_material_item_details(row.item_code, self.source_warehouse)
            row.item_name = details["item_name"]
            row.material_category = details["material_category"]
            row.stock_uom = details["stock_uom"]
            row.stock_qty_kg = details["stock_qty_kg"]
            row.issue_qty_g = flt(row.issue_qty_g)
            if row.issue_qty_g <= 0:
                frappe.throw(_("物料 {0} 的出库数量必须大于 0").format(row.item_name or row.item_code))
            row.issue_qty_kg = flt(row.issue_qty_g / 1000, 6)
            totals_by_item[row.item_code] = totals_by_item.get(row.item_code, 0) + row.issue_qty_kg
        for item_code, qty in totals_by_item.items():
            available = flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": self.source_warehouse}, "actual_qty") or 0)
            if qty > available:
                frappe.throw(_("物料 {0} 库存不足，库存 {1} kg，本次需出库 {2} kg").format(item_code, available, qty))

    def _set_totals(self):
        self.total_issue_qty_g = sum(flt(row.issue_qty_g) for row in self.items)
        self.total_issue_qty_kg = flt(self.total_issue_qty_g / 1000, 6)

    def _set_item_names(self):
        names = []
        for row in self.items:
            name = (row.item_name or row.item_code or "").strip()
            if name and name not in names:
                names.append(name)
        self.item_names = "、".join(names)

    def _create_stock_entry(self):
        if self.stock_entry:
            return
        company = frappe.db.get_value("Warehouse", self.source_warehouse, "company")
        entry = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Issue",
            "purpose": "Material Issue",
            "company": company,
            "posting_date": self.issue_date,
            "remarks": _("染料其他出库单：{0}；用途：{1}；领用部门：{2}；领用人：{3}").format(
                self.name, self.issue_purpose, self.department, self.recipient
            ),
            "items": [{
                "item_code": row.item_code,
                "qty": row.issue_qty_kg,
                "uom": row.stock_uom,
                "s_warehouse": self.source_warehouse,
                "allow_zero_valuation_rate": 1,
                "custom_production_flow_card": self.production_flow_card,
                "custom_dye_material_other_issue": self.name,
            } for row in self.items],
        })
        entry.insert(ignore_permissions=True)
        entry.submit()
        self.db_set("stock_entry", entry.name, update_modified=False)
        self.stock_entry = entry.name


_LIST_COLUMN_WIDTHS_KEY = "dye_material_other_issue_list_column_widths"
_LIST_COLUMN_WIDTHS_MIN = 20
_LIST_COLUMN_WIDTHS_MAX = 600


@frappe.whitelist()
def get_dye_material_other_issue_list_column_widths():
    return frappe.parse_json(frappe.db.get_global(_LIST_COLUMN_WIDTHS_KEY) or "{}")


@frappe.whitelist()
def set_dye_material_other_issue_list_column_widths(widths):
    frappe.only_for("System Manager")
    widths = frappe.parse_json(widths) or {}
    allowed_fields = {
        field.fieldname
        for field in frappe.get_meta("Dye Material Other Issue").fields
        if field.fieldname
    }
    allowed_fields.update({"name", "__status"})
    cleaned_widths = {}
    for fieldname, width in widths.items():
        width = flt(width)
        if fieldname not in allowed_fields or not width:
            continue
        if not _LIST_COLUMN_WIDTHS_MIN <= width <= _LIST_COLUMN_WIDTHS_MAX:
            frappe.throw(_("列宽应在 {0} 至 {1} 之间").format(_LIST_COLUMN_WIDTHS_MIN, _LIST_COLUMN_WIDTHS_MAX))
        cleaned_widths[fieldname] = int(width)
    frappe.db.set_global(_LIST_COLUMN_WIDTHS_KEY, frappe.as_json(cleaned_widths))
    return cleaned_widths


def clear_other_issue_link_before_stock_entry_cancel(doc, method=None):
    """Remove only the reverse link that would block automatic Stock Entry cancellation."""
    if not any(row.get("custom_dye_material_other_issue") for row in doc.items):
        return

    frappe.db.sql(
        """
        UPDATE `tabStock Entry Detail`
        SET custom_dye_material_other_issue = NULL
        WHERE parent = %s
          AND IFNULL(custom_dye_material_other_issue, '') != ''
        """,
        (doc.name,),
    )
    for row in doc.items:
        row.custom_dye_material_other_issue = None


@frappe.whitelist()
def get_dye_material_item_details(item_code, warehouse):
    item = frappe.db.get_value("Item", item_code, ["item_name", "item_group", "stock_uom", "disabled"], as_dict=True)
    if not item or item.disabled or not _get_material_category(item.item_group):
        frappe.throw(_("只能选择启用的染料或助剂物料"))
    qty = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty") or 0
    return {"item_name": item.item_name, "material_category": _get_material_category(item.item_group), "stock_uom": item.stock_uom, "stock_qty_kg": flt(qty)}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_dye_material_items(doctype, txt, searchfield, start, page_len, filters):
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


def _get_material_category(item_group):
    group = frappe.db.get_value("Item Group", item_group, ["lft", "rgt"], as_dict=True)
    if not group:
        return None
    for category in DYE_MATERIAL_GROUPS:
        root = frappe.db.get_value("Item Group", category, ["lft", "rgt"], as_dict=True)
        if root and root.lft <= group.lft and group.rgt <= root.rgt:
            return category
    return None
