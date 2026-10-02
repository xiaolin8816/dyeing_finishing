import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt, now_datetime


class ProductionFlowCard(Document):
    def autoname(self):
        self.name = make_autoname("YY.MM.DD.###")
        self.flow_card_no = self.name

    def before_insert(self):
        self.flow_card_no = self.name
        self.barcode = self.barcode or self.name
        self._set_document_status()

    def validate(self):
        self.flow_card_no = self.flow_card_no or self.name
        self.barcode = self.barcode or self.flow_card_no
        self._refresh_grey_fabric_stock()
        self._set_operation_summary()
        self._set_document_status()

    def before_submit(self):
        self._set_document_status("已审核")

    def on_cancel(self):
        self.db_set("document_status", "未审核", update_modified=False)

    def _set_document_status(self, value=None):
        self.document_status = value or ("已审核" if self.docstatus == 1 else "保存")

    def _set_operation_summary(self):
        operations = sorted(self.get("operations") or [], key=lambda row: row.sequence_no or 0)
        pending = next((row for row in operations if row.operation_status != "已完成"), None)
        self.current_operation = pending.operation if pending else ""
        self.is_completed = 1 if operations and not pending else 0

    def _refresh_grey_fabric_stock(self):
        for row in self.get("grey_fabric_issues") or []:
            if not row.batch_no:
                continue
            detail = get_batch_stock_details(row.batch_no, self.customer, self.order_type)
            if not detail:
                frappe.throw(_("批次 {0} 没有符合条件的可用胚布库存").format(row.batch_no))
            row.grey_fabric_name = detail.grey_fabric_name
            row.color = detail.color
            row.stock_roll_count = detail.stock_roll_count
            row.stock_qty = detail.stock_qty
            row.warehouse = detail.warehouse
            row.location = detail.location
            if flt(row.planned_roll_count) > flt(row.stock_roll_count):
                frappe.throw(_("批次 {0} 的计划领用匹数不能大于库存匹数").format(row.batch_no))
            if flt(row.planned_qty) > flt(row.stock_qty):
                frappe.throw(_("批次 {0} 的计划领用数量不能大于库存数量").format(row.batch_no))


def _batch_stock_query(customer=None, order_type=None, batch_no=None, location=None):
    customer_condition = "COALESCE(receipt.customer, '') = %(customer)s" if order_type == "来料加工" else "COALESCE(receipt.customer, '') = ''"
    batch_condition = "AND stock.batch_no = %(batch_no)s" if batch_no else ""
    location_condition = "AND stock.location = %(location)s" if location else ""
    return frappe.db.sql(
        f"""
        SELECT stock.batch_no, stock.item_code, stock.item_name AS grey_fabric_name, stock.color,
            COALESCE(master.specification, '') AS specification, stock.stock_roll_count, stock.stock_qty, '胚布仓库 - 沅泰' AS warehouse,
            stock.location
        FROM (
            SELECT COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no) AS batch_no,
                sle.item_code, MAX(item.item_name) AS item_name,
                MAX(receipt_item.color) AS color,
                GREATEST(MAX(receipt_rolls.stock_roll_count) - COALESCE(MAX(issued_rolls.issue_roll_count), 0), 0) AS stock_roll_count,
                SUM(sle.actual_qty) AS stock_qty,
                sle.warehouse AS location
            FROM `tabStock Ledger Entry` sle
            INNER JOIN `tabItem` item ON item.name = sle.item_code
            LEFT JOIN `tabSerial and Batch Entry` bundle_entry ON bundle_entry.parent = sle.serial_and_batch_bundle
            LEFT JOIN `tabCustomer Grey Fabric Receipt Item` receipt_item
                ON receipt_item.batch_no = COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no)
            LEFT JOIN `tabCustomer Grey Fabric Receipt` receipt
                ON receipt.name = receipt_item.parent AND receipt.docstatus = 1
            LEFT JOIN (
                SELECT receipt_item.batch_no, SUM(receipt_item.roll_count) AS stock_roll_count
                FROM `tabCustomer Grey Fabric Receipt Item` receipt_item
                INNER JOIN `tabCustomer Grey Fabric Receipt` receipt
                    ON receipt.name = receipt_item.parent AND receipt.docstatus = 1
                WHERE receipt_item.batch_no IS NOT NULL AND receipt_item.batch_no != ''
                GROUP BY receipt_item.batch_no
            ) receipt_rolls ON receipt_rolls.batch_no = COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no)
            LEFT JOIN (
                SELECT issue_item.batch_no, SUM(issue_item.issue_roll_count) AS issue_roll_count
                FROM `tabGrey Fabric Issue Item` issue_item
                INNER JOIN `tabGrey Fabric Issue` issue ON issue.name = issue_item.parent AND issue.docstatus = 1
                GROUP BY issue_item.batch_no
            ) issued_rolls ON issued_rolls.batch_no = COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no)
            WHERE sle.is_cancelled = 0
                AND COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no) IS NOT NULL
                AND COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no) != ''
                AND item.item_group IN (
                    SELECT name FROM `tabItem Group`
                    WHERE lft >= (SELECT lft FROM `tabItem Group` WHERE name = '胚布')
                    AND rgt <= (SELECT rgt FROM `tabItem Group` WHERE name = '胚布')
                )
            GROUP BY COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no), sle.item_code, sle.warehouse
            HAVING SUM(sle.actual_qty) > 0
        ) stock
        LEFT JOIN `tabGrey Fabric Master` master ON master.name = stock.item_code
        LEFT JOIN `tabCustomer Grey Fabric Receipt Item` receipt_item ON receipt_item.batch_no = stock.batch_no
        LEFT JOIN `tabCustomer Grey Fabric Receipt` receipt ON receipt.name = receipt_item.parent AND receipt.docstatus = 1
        WHERE {customer_condition} {batch_condition} {location_condition}
        ORDER BY stock.batch_no, stock.stock_qty DESC
        """,
        {"customer": customer or "", "batch_no": batch_no or "", "location": location or ""},
        as_dict=True,
    )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_available_grey_fabric_batches(doctype, txt, searchfield, start, page_len, filters):
    filters = frappe.parse_json(filters) or {}
    rows = _batch_stock_query(filters.get("customer"), filters.get("order_type"))
    return [(row.batch_no, row.grey_fabric_name, row.color, row.location) for row in rows if txt.lower() in row.batch_no.lower()][start : start + page_len]


@frappe.whitelist()
def get_batch_stock_details(batch_no, customer=None, order_type=None, location=None):
    rows = _batch_stock_query(customer, order_type, batch_no, location)
    return rows[0] if rows else None


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_sales_order_items(doctype, txt, searchfield, start, page_len, filters):
    filters = frappe.parse_json(filters) or {}
    sales_order = filters.get("sales_order")
    if not sales_order:
        return []
    return frappe.db.sql(
        """SELECT name, item_code, item_name
        FROM `tabSales Order Item`
        WHERE parent = %(sales_order)s AND parenttype = 'Sales Order' AND name LIKE %(txt)s
        ORDER BY idx LIMIT %(page_len)s OFFSET %(start)s""",
        {"sales_order": sales_order, "txt": f"%{txt}%", "page_len": page_len, "start": start},
    )


@frappe.whitelist()
def get_sales_order_item_details(sales_order, sales_order_item):
    order = frappe.get_doc("Sales Order", sales_order)
    item = next((row for row in order.items if row.name == sales_order_item), None)
    if not item:
        frappe.throw(_("销售订单明细不属于当前销售订单"))
    return {
        "customer": order.customer,
        "customer_order_no": order.get("custom_customer_order_no") or order.get("po_no") or "",
        "order_date": order.transaction_date,
        "delivery_date": order.delivery_date,
        "order_type": order.get("custom_dyeing_order_type") or "",
        "process_type": item.get("custom_process_type") or "",
        "color_no": item.get("custom_color_no") or "",
        "color": item.get("custom_color") or "",
        "finished_product_name": item.get("custom_color_product_name") or item.item_name or "",
        "finished_width": item.get("custom_finished_width") or "",
        "finished_gsm": item.get("custom_finished_gsm") or "",
        "finished_uom": item.uom or "",
        "finished_specification": item.get("custom_finished_specification") or "",
        "order_qty": item.qty or 0,
        "order_remarks": order.get("terms") or "",
        "process_requirements": [
            {"process_requirement": row.process_requirement, "process_requirement_name": row.process_requirement_name}
            for row in (order.get("custom_process_requirements") or [])
        ],
        "packaging_requirements": [
            {"packaging_requirement": row.packaging_requirement, "packaging_requirement_name": row.packaging_requirement_name}
            for row in (order.get("custom_packaging_requirements") or [])
        ],
    }


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_process_requirements_for_selection(doctype, txt, searchfield, start, page_len, filters, as_dict=False, **kwargs):
    return frappe.db.sql(
        """SELECT name, process_requirement_code, process_requirement_name
        FROM `tabProcess Requirement`
        WHERE disabled = 0
          AND (
              name LIKE %(txt)s
              OR process_requirement_code LIKE %(txt)s
              OR process_requirement_name LIKE %(txt)s
          )
        ORDER BY process_requirement_code
        LIMIT %(page_len)s OFFSET %(start)s""",
        {"txt": f"%{txt}%", "page_len": page_len, "start": start},
        as_dict=as_dict,
    )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_packaging_requirements_for_selection(doctype, txt, searchfield, start, page_len, filters, as_dict=False, **kwargs):
    return frappe.db.sql(
        """SELECT name, packaging_requirement_code, packaging_requirement_name
        FROM `tabPackaging Requirement`
        WHERE disabled = 0
          AND (
              name LIKE %(txt)s
              OR packaging_requirement_code LIKE %(txt)s
              OR packaging_requirement_name LIKE %(txt)s
          )
        ORDER BY packaging_requirement_code
        LIMIT %(page_len)s OFFSET %(start)s""",
        {"txt": f"%{txt}%", "page_len": page_len, "start": start},
        as_dict=as_dict,
    )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_production_operations_for_selection(doctype, txt, searchfield, start, page_len, filters, as_dict=False, **kwargs):
    return frappe.db.sql(
        """SELECT name, production_operation_code, production_operation_name, sequence_no
        FROM `tabProduction Operation`
        WHERE disabled = 0
          AND COALESCE(sequence_no, '') != ''
          AND (
              name LIKE %(txt)s
              OR production_operation_code LIKE %(txt)s
              OR production_operation_name LIKE %(txt)s
          )
        ORDER BY CAST(NULLIF(sequence_no, '') AS UNSIGNED), production_operation_code
        LIMIT %(page_len)s OFFSET %(start)s""",
        {"txt": f"%{txt}%", "page_len": page_len, "start": start},
        as_dict=as_dict,
    )

_LIST_COLUMN_WIDTHS_KEY = "production_flow_card_list_column_widths"
_LIST_COLUMN_WIDTHS_MIN = 20
_LIST_COLUMN_WIDTHS_MAX = 600


@frappe.whitelist()
def get_production_flow_card_list_column_widths():
    return frappe.parse_json(frappe.db.get_global(_LIST_COLUMN_WIDTHS_KEY) or "{}")


@frappe.whitelist()
def set_production_flow_card_list_column_widths(widths):
    frappe.only_for("System Manager")
    widths = frappe.parse_json(widths) or {}
    allowed_fields = {
        field.fieldname
        for field in frappe.get_meta("Production Flow Card").fields
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



def record_production_progress(flow_card, operation, progress_status, source_doctype, source_document,
                               batch_no="", quantity=0, uom="", dyeing_machine="",
                               material_sheet_type="", dyeing_sequence=0, description=""):
    if not flow_card:
        return
    card = frappe.get_doc("Production Flow Card", flow_card)
    if card.docstatus == 2:
        return
    progress = frappe.get_doc({
        "doctype": "Production Flow Card Progress",
        "parent": card.name,
        "parenttype": "Production Flow Card",
        "parentfield": "progress_records",
        "docstatus": card.docstatus,
        "progress_time": now_datetime(),
        "operation": operation,
        "progress_status": progress_status,
        "source_doctype": source_doctype,
        "source_document": source_document,
        "batch_no": batch_no,
        "quantity": flt(quantity),
        "uom": uom,
        "dyeing_machine": dyeing_machine,
        "material_sheet_type": material_sheet_type,
        "dyeing_sequence": dyeing_sequence,
        "operator": frappe.session.user,
        "description": description,
    })
    progress.insert(ignore_permissions=True)
    frappe.db.set_value("Production Flow Card", card.name, {
        "current_progress_status": progress_status,
        "latest_progress_time": progress.progress_time,
        "latest_source_doctype": source_doctype,
        "latest_source_document": source_document,
    }, update_modified=False)


def remove_production_progress(source_doctype, source_document):
    records = frappe.get_all(
        "Production Flow Card Progress",
        filters={"source_doctype": source_doctype, "source_document": source_document},
        fields=["parent"],
    )
    flow_cards = {record.parent for record in records if record.parent}
    if not flow_cards:
        return

    frappe.db.delete(
        "Production Flow Card Progress",
        {"source_doctype": source_doctype, "source_document": source_document},
    )
    for flow_card in flow_cards:
        latest = frappe.get_all(
            "Production Flow Card Progress",
            filters={"parent": flow_card},
            fields=["progress_status", "progress_time", "source_doctype", "source_document"],
            order_by="progress_time desc, creation desc",
            limit=1,
        )
        values = {
            "current_progress_status": latest[0].progress_status if latest else "",
            "latest_progress_time": latest[0].progress_time if latest else None,
            "latest_source_doctype": latest[0].source_doctype if latest else "",
            "latest_source_document": latest[0].source_document if latest else "",
        }
        frappe.db.set_value("Production Flow Card", flow_card, values, update_modified=False)
