from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate

from dyeing_finishing.dyeing_finishing.doctype.production_flow_card.production_flow_card import _batch_stock_query

TARGET_WAREHOUSE = "进行中 - 沅泰"


class GreyFabricIssue(Document):
    def before_insert(self):
        self.document_number = self.name
        self.outbound_date = self.outbound_date or getdate(nowdate())
        self._set_document_status()

    def validate(self):
        self.document_number = self.name
        self.outbound_date = self.outbound_date or getdate(nowdate())
        self._set_document_status()
        self._set_flow_card_details()
        self._validate_items()
        self._set_totals()

    def before_submit(self):
        self._set_document_status("已提交")
        self._validate_items()
        self._set_totals()

    def on_submit(self):
        self._create_stock_entry()

    def on_cancel(self):
        if self.stock_entry:
            entry = frappe.get_doc("Stock Entry", self.stock_entry)
            if entry.docstatus == 1:
                entry.cancel()
        self.db_set("document_status", "已取消", update_modified=False)

    def _set_document_status(self, value=None):
        self.document_status = value or ("已提交" if self.docstatus == 1 else "保存")

    def _set_flow_card_details(self):
        if not self.flow_card:
            frappe.throw(_("请选择生产流转卡"))
        card = frappe.get_doc("Production Flow Card", self.flow_card)
        if card.docstatus == 2:
            frappe.throw(_("不能引用已取消的生产流转卡"))
        self.sales_order = card.sales_order
        self.customer = card.customer
        self.customer_name = frappe.db.get_value("Customer", card.customer, "customer_name") or card.customer
        self.color_no = card.color_no
        self.color = card.color
        self.finished_product_name = card.finished_product_name
        self.finished_specification = card.finished_specification

    def _validate_items(self):
        if not self.items:
            frappe.throw(_("请至少填写一条胚布出库明细"))
        card = frappe.get_doc("Production Flow Card", self.flow_card)
        plans = {row.name: row for row in card.get("grey_fabric_issues") or []}
        by_batch = defaultdict(lambda: {"rolls": 0.0, "qty": 0.0})
        for row in self.items:
            plan = plans.get(row.flow_card_grey_fabric_issue)
            if not plan:
                frappe.throw(_("第 {0} 行未关联有效的流转卡胚布领用明细").format(row.idx))
            if not row.batch_no:
                frappe.throw(_("第 {0} 行请选择批次").format(row.idx))
            if flt(row.issue_roll_count) < 0 or flt(row.issue_qty) < 0:
                frappe.throw(_("第 {0} 行出库匹数和数量不能小于 0").format(row.idx))
            if not flt(row.issue_roll_count) and not flt(row.issue_qty):
                frappe.throw(_("第 {0} 行请填写本次出库匹数或数量").format(row.idx))
            detail = get_batch_stock_details(row.batch_no, self.customer, plan.location)
            if not detail:
                frappe.throw(_("第 {0} 行批次 {1} 不属于当前客户或没有可用胚布库存").format(row.idx, row.batch_no))
            if plan.grey_fabric_name and detail.grey_fabric_name != plan.grey_fabric_name:
                frappe.throw(_("第 {0} 行批次胚布名称与流转卡领用计划不一致").format(row.idx))
            if plan.color and detail.color and detail.color.strip() != plan.color.strip():
                frappe.throw(_("第 {0} 行批次颜色与流转卡领用计划不一致").format(row.idx))
            set_row_details(row, plan, detail, self.flow_card, self.name)
            by_batch[row.batch_no]["rolls"] += flt(row.issue_roll_count)
            by_batch[row.batch_no]["qty"] += flt(row.issue_qty)
        for batch, values in by_batch.items():
            row = next(item for item in self.items if item.batch_no == batch)
            if values["rolls"] > flt(row.stock_roll_count):
                frappe.throw(_("批次 {0} 的本次出库匹数超过可用库存匹数").format(batch))
            if values["qty"] > flt(row.stock_qty):
                frappe.throw(_("批次 {0} 的本次出库数量超过可用库存数量").format(batch))

    def _set_totals(self):
        self.issue_roll_count = sum(flt(row.issue_roll_count) for row in self.items)
        self.issue_qty = sum(flt(row.issue_qty) for row in self.items)
        historical = get_issue_totals(self.flow_card, exclude_name=self.name)
        self.cumulative_roll_count = historical.rolls + self.issue_roll_count
        self.cumulative_qty = historical.qty + self.issue_qty
        self.is_over_planned = "是" if any(
            flt(row.issued_roll_count) + flt(row.issue_roll_count) > flt(row.planned_roll_count)
            or flt(row.issued_qty) + flt(row.issue_qty) > flt(row.planned_qty)
            for row in self.items
        ) else "否"

    def _create_stock_entry(self):
        if self.stock_entry:
            return
        if not frappe.db.exists("Warehouse", TARGET_WAREHOUSE):
            frappe.throw(_("未找到生产中转仓：{0}").format(TARGET_WAREHOUSE))
        company = frappe.db.get_value("Warehouse", TARGET_WAREHOUSE, "company")
        stock_items = []
        for row in self.items:
            if not flt(row.issue_qty):
                continue
            stock_items.append({"item_code":row.item_code,"qty":flt(row.issue_qty),"uom":frappe.db.get_value("Item",row.item_code,"stock_uom"),"s_warehouse":row.location,"t_warehouse":TARGET_WAREHOUSE,"batch_no":row.batch_no,"allow_zero_valuation_rate":1})
        if not stock_items:
            frappe.throw(_("没有可生成库存转移的出库数量"))
        entry = frappe.get_doc({"doctype":"Stock Entry","stock_entry_type":"Material Transfer","purpose":"Material Transfer","company":company,"posting_date":self.outbound_date,"to_warehouse":TARGET_WAREHOUSE,"remarks":_("胚布出库单：{0}；生产流转卡：{1}").format(self.name,self.flow_card),"items":stock_items})
        entry.insert(ignore_permissions=True)
        entry.submit()
        self.db_set("stock_entry", entry.name, update_modified=False)


class Totals:
    def __init__(self, rolls=0, qty=0):
        self.rolls = flt(rolls)
        self.qty = flt(qty)


def get_issue_totals(flow_card, source_row=None, exclude_name=None):
    where = ["parent.flow_card = %(flow_card)s", "parent.docstatus = 1"]
    values = {"flow_card": flow_card}
    if source_row:
        where.append("item.flow_card_grey_fabric_issue = %(source_row)s")
        values["source_row"] = source_row
    if exclude_name:
        where.append("parent.name != %(exclude_name)s")
        values["exclude_name"] = exclude_name
    query = "SELECT COALESCE(SUM(item.issue_roll_count), 0) AS rolls, COALESCE(SUM(item.issue_qty), 0) AS qty FROM `tabGrey Fabric Issue Item` item INNER JOIN `tabGrey Fabric Issue` parent ON parent.name = item.parent WHERE " + " AND ".join(where)
    result = frappe.db.sql(query, values, as_dict=True)[0]
    return Totals(result.rolls, result.qty)


def get_batch_stock_details(batch_no, customer, location=None):
    rows = _batch_stock_query(customer, "来料加工", batch_no=batch_no, location=location)
    return rows[0] if rows else None


def set_row_details(row, plan, detail, flow_card, exclude_name=None):
    total = get_issue_totals(flow_card, plan.name, exclude_name)
    row.item_code, row.grey_fabric_name, row.specification, row.color = detail.item_code, detail.grey_fabric_name, detail.specification, detail.color
    row.stock_roll_count, row.stock_qty = detail.stock_roll_count, detail.stock_qty
    row.planned_roll_count, row.planned_qty = plan.planned_roll_count, plan.planned_qty
    row.issued_roll_count, row.issued_qty = total.rolls, total.qty
    row.warehouse, row.location = detail.warehouse, detail.location
    row.shortage_roll_count = max(flt(plan.planned_roll_count) - total.rolls - flt(row.issue_roll_count), 0)
    row.shortage_qty = max(flt(plan.planned_qty) - total.qty - flt(row.issue_qty), 0)


def get_flow_card_details(flow_card):
    card = frappe.get_doc("Production Flow Card", flow_card)
    if card.docstatus == 2:
        frappe.throw(_("不能引用已取消的生产流转卡"))
    result = {"sales_order":card.sales_order,"customer":card.customer,"customer_name":frappe.db.get_value("Customer",card.customer,"customer_name") or card.customer,"color_no":card.color_no,"color":card.color,"finished_product_name":card.finished_product_name,"finished_specification":card.finished_specification,"items":[],"plan_rows":[]}
    for plan in card.get("grey_fabric_issues") or []:
        result["plan_rows"].append({"name":plan.name,"grey_fabric_name":plan.grey_fabric_name,"color":plan.color,"planned_roll_count":plan.planned_roll_count,"planned_qty":plan.planned_qty,"warehouse":plan.warehouse,"location":plan.location})
        if not plan.batch_no:
            continue
        detail = get_batch_stock_details(plan.batch_no, card.customer, plan.location)
        if not detail:
            continue
        total = get_issue_totals(card.name, plan.name)
        remaining_rolls, remaining_qty = max(flt(plan.planned_roll_count)-total.rolls,0), max(flt(plan.planned_qty)-total.qty,0)
        result["items"].append({"flow_card_grey_fabric_issue":plan.name,"source_type":"自动带出","batch_no":plan.batch_no,"item_code":detail.item_code,"grey_fabric_name":detail.grey_fabric_name,"specification":detail.specification,"color":detail.color,"stock_roll_count":detail.stock_roll_count,"stock_qty":detail.stock_qty,"planned_roll_count":plan.planned_roll_count,"planned_qty":plan.planned_qty,"issued_roll_count":total.rolls,"issued_qty":total.qty,"issue_roll_count":min(remaining_rolls,flt(detail.stock_roll_count)),"issue_qty":min(remaining_qty,flt(detail.stock_qty)),"warehouse":detail.warehouse,"location":detail.location,"shortage_roll_count":max(remaining_rolls-flt(detail.stock_roll_count),0),"shortage_qty":max(remaining_qty-flt(detail.stock_qty),0)})
    return result


@frappe.whitelist()
def get_grey_fabric_issue_flow_card_details(flow_card):
    return get_flow_card_details(flow_card)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_available_grey_fabric_batches(doctype, txt, searchfield, start, page_len, filters):
    filters = frappe.parse_json(filters) or {}
    if not filters.get("flow_card") or not filters.get("source_row"):
        return []
    card = frappe.get_doc("Production Flow Card", filters.get("flow_card"))
    plan = next((row for row in card.get("grey_fabric_issues") or [] if row.name == filters.get("source_row")), None)
    if not plan:
        return []
    rows = _batch_stock_query(card.customer, "来料加工", location=plan.location)
    return [(row.batch_no,row.grey_fabric_name,row.color,row.location) for row in rows if (not plan.grey_fabric_name or row.grey_fabric_name == plan.grey_fabric_name) and (not plan.color or not row.color or row.color.strip() == plan.color.strip()) and txt.lower() in row.batch_no.lower()][start:start+page_len]


@frappe.whitelist()
def get_grey_fabric_issue_batch_details(batch_no, customer, location=None):
    detail = get_batch_stock_details(batch_no, customer, location)
    if not detail:
        frappe.throw(_("未找到当前客户名下的可用胚布批次"))
    return detail
