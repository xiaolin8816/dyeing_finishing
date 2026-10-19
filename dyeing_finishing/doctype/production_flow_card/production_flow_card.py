import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt, now_datetime
from dyeing_finishing.dyeing_finishing.settings import get_setting


class ProductionFlowCard(Document):
    def autoname(self):
        if self.flow_card_type == "回修":
            self.name = _next_rework_flow_card_name(self)
        else:
            self.name = make_autoname("YY.MM.DD.###")
        self.flow_card_no = self.name

    def before_insert(self):
        self.flow_card_no = self.name
        self.barcode = self.barcode or self.name
        self._set_company()
        self._set_document_status()

    def validate(self):
        self.flow_card_no = self.flow_card_no or self.name
        self.barcode = self.barcode or self.flow_card_no
        self._set_company()
        self._set_finished_specification()
        self._validate_operations()
        self._validate_rework_source()
        self._set_flow_card_qty()
        self._refresh_grey_fabric_stock()
        self._set_operation_summary()
        self._set_production_status()
        self._set_document_status()

    def _set_company(self):
        if self.sales_order:
            self.company = frappe.db.get_value("Dyeing Sales Order", self.sales_order, "company") or self.company
        self.company = self.company or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
            "Global Defaults", "default_company"
        )

    def before_submit(self):
        self._set_document_status("已审核")

    def on_cancel(self):
        downstream_documents = _get_submitted_downstream_documents(self.name)
        if downstream_documents:
            names = "、".join(name for _, name in downstream_documents)
            frappe.throw(_("生产流转卡已关联已提交的下游单据 {0}，请先处理下游单据后再取消").format(names))

        # 未产生实际下游业务时，取消即恢复草稿，允许在原流转卡修正后重新提交。
        self.db_set(
            {
                "docstatus": 0,
                "document_status": "保存",
                "production_status": "进行中",
                "closure_date": None,
                "closure_reason": "",
                "closure_remarks": "",
                "closed_by": "",
            },
            update_modified=False,
        )
        quote = chr(96)
        for table in (
            "tabProduction Flow Card Grey Fabric Issue",
            "tabProduction Flow Card Process Requirement",
            "tabProduction Flow Card Packaging Requirement",
            "tabProduction Flow Card Operation",
            "tabProduction Flow Card Progress",
        ):
            frappe.db.sql(
                f"UPDATE {quote}{table}{quote} SET docstatus = 0 "
                "WHERE parent = %s AND parenttype = 'Production Flow Card'",
                self.name,
            )
        self.docstatus = 0
        self.document_status = "保存"
        self.production_status = "进行中"
        for table_field in ("grey_fabric_issues", "process_requirements", "packaging_requirements", "operations", "progress_records"):
            for row in self.get(table_field) or []:
                row.docstatus = 0
        self.add_comment("Edit", _("未关联已提交下游单据，流转卡已恢复为草稿，可修改后重新提交。"))

    def _set_document_status(self, value=None):
        self.document_status = value or ("已审核" if self.docstatus == 1 else "保存")

    def _set_production_status(self):
        self.production_status = self.production_status or "进行中"

    def _set_finished_specification(self):
        width = str(self.finished_width or "").strip()
        gsm = str(self.finished_gsm or "").strip()
        if gsm and not self.finished_gsm_uom:
            self.finished_gsm_uom = "g/㎡"
        gsm_value = f"{gsm}{self.finished_gsm_uom or ''}" if gsm else ""
        self.finished_specification = "*".join(
            value for value in (width, gsm_value) if value
        )

    def _validate_operations(self):
        if not self.get("operations"):
            frappe.throw(_("请至少选择一道生产工序"))
        self._validate_unique_child_links()

    def _validate_unique_child_links(self):
        for table_field, link_field, label in (
            ("process_requirements", "process_requirement", "加工要求"),
            ("packaging_requirements", "packaging_requirement", "包装要求"),
            ("operations", "operation", "生产工序"),
        ):
            values = [row.get(link_field) for row in self.get(table_field) or [] if row.get(link_field)]
            duplicates = list(dict.fromkeys(value for value in values if values.count(value) > 1))
            if duplicates:
                frappe.throw(_("{0}不能重复选择：{1}").format(label, "、".join(duplicates)))


    def _set_flow_card_qty(self):
        if self.flow_card_type == "回修":
            return
        if not self.sales_order_item:
            return
        order_qty = frappe.db.get_value(
            "Dyeing Sales Order Item",
            {"name": self.sales_order_item, "parent": self.sales_order},
            "qty",
        )
        if order_qty is None:
            frappe.throw(_("染整销售订单明细不属于当前染整销售订单"))
        if order_qty is not None:
            self.order_qty = flt(order_qty)
            self.production_qty = flt(order_qty)

    def _set_operation_summary(self):
        # Browser requests may send Int fields as strings (for example "01").
        # Normalize the sort key so restored drafts can mix existing numeric rows
        # with newly selected operations without comparing str and int values.
        operations = sorted(
            self.get("operations") or [],
            key=lambda row: (flt(row.sequence_no), flt(row.idx)),
        )
        for index, row in enumerate(operations, 1):
            row.idx = index
        self.set("operations", operations)
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
            row.color = self.color if self.flow_card_type == "回修" else detail.color
            row.stock_roll_count = detail.stock_roll_count
            row.stock_qty = detail.stock_qty
            row.warehouse = detail.warehouse
            row.location = detail.location
            if flt(row.planned_roll_count) > flt(row.stock_roll_count):
                frappe.throw(_("批次 {0} 的计划领用匹数不能大于库存匹数").format(row.batch_no))
            if flt(row.planned_qty) > flt(row.stock_qty):
                frappe.throw(_("批次 {0} 的计划领用数量不能大于库存数量").format(row.batch_no))

    def _validate_rework_source(self):
        if self.flow_card_type != "回修":
            return
        source_doctype, source_name = _get_rework_source_reference(self)
        source = frappe.get_doc(source_doctype, source_name)
        if source.docstatus != 1:
            frappe.throw(_("只能引用已提交的转胚布仓单"))
        if (source.production_flow_card or "").rstrip("H") != self.original_flow_card:
            frappe.throw(_("回修来源与原始生产流转卡不一致"))
        returned_color = _get_returned_product_color(source.name) if source_doctype == "Finished Product Return to Grey Fabric" else source.color
        if self.color_no:
            color = frappe.db.get_value(
                "Color Master",
                self.color_no,
                ["color_name", "customer_name", "status"],
                as_dict=True,
            )
            if not color or color.status != "启用":
                frappe.throw(_("色号 {0} 不存在或已停用").format(self.color_no))
            if color.customer_name != self.customer:
                frappe.throw(_("色号 {0} 不属于当前客户").format(self.color_no))
            self.color = color.color_name
        elif returned_color:
            self.color = returned_color
        for row in self.get("grey_fabric_issues") or []:
            row.color = self.color
        source_field = "source_return_to_grey_fabric" if source_doctype == "Finished Product Return to Grey Fabric" else "source_finished_product_to_grey_fabric"
        duplicate = frappe.db.exists("Production Flow Card", {
            source_field: source.name,
            "name": ["!=", self.name],
            "docstatus": ["<", 2],
        })
        if duplicate:
            frappe.throw(_("该转胚布仓单已生成回修流转卡 {0}").format(duplicate))


def _get_rework_source_reference(doc):
    sources = [
        ("Finished Product Return to Grey Fabric", doc.get("source_return_to_grey_fabric")),
        ("Finished Product to Grey Fabric", doc.get("source_finished_product_to_grey_fabric")),
    ]
    selected = [(doctype, name) for doctype, name in sources if name]
    if len(selected) != 1:
        frappe.throw(_("回修流转卡必须且只能选择一种转胚布仓来源"))
    return selected[0]


def _next_rework_flow_card_name(doc):
    source_doctype, source_name = _get_rework_source_reference(doc)
    source = frappe.db.get_value(
        source_doctype, source_name,
        ["production_flow_card", "docstatus"], as_dict=True,
    )
    if not source or source.docstatus != 1:
        frappe.throw(_("转胚布仓单不存在或尚未提交"))
    root = (source.production_flow_card or "").rstrip("H")
    if not root:
        frappe.throw(_("无法确定原始生产流转卡"))
    existing = frappe.get_all(
        "Production Flow Card",
        filters={"original_flow_card": root, "flow_card_type": "回修"},
        pluck="name",
    )
    rework_count = max([len(name) - len(root) for name in existing if name.startswith(root) and set(name[len(root):]) <= {"H"}] or [0]) + 1
    doc.original_flow_card = root
    doc.previous_flow_card = root + ("H" * (rework_count - 1))
    doc.rework_count = rework_count
    return root + ("H" * rework_count)


def ensure_flow_card_open(card):
    if card.docstatus == 2:
        frappe.throw(_("不能引用已取消的生产流转卡"))
    if card.docstatus != 1:
        frappe.throw(_("生产流转卡 {0} 尚未提交，不能新增后续业务单据").format(card.name))
    if (card.production_status or "进行中") == "已关闭":
        frappe.throw(_("生产流转卡 {0} 已关闭，不能新增后续业务单据。如需继续生产，请先重新开启生产。").format(card.name))


@frappe.whitelist()
def get_rework_source_details(source_return_to_grey_fabric):
    source = frappe.get_doc("Finished Product Return to Grey Fabric", source_return_to_grey_fabric)
    source.check_permission("read")
    if source.docstatus != 1:
        frappe.throw(_("只能引用已提交的成品退货转胚布仓单"))
    if frappe.db.exists("Production Flow Card", {
        "source_return_to_grey_fabric": source.name, "docstatus": ["<", 2]
    }):
        frappe.throw(_("该退货转胚布仓单已生成回修流转卡"))

    original_name = (source.production_flow_card or "").rstrip("H")
    original = frappe.get_doc("Production Flow Card", original_name)
    original.check_permission("read")
    scalar_fields = (
        "sales_order", "sales_order_item", "customer", "customer_order_no", "order_date",
        "delivery_date", "order_type", "process_type", "color_no", "color",
        "finished_product_name", "finished_width", "finished_gsm", "finished_gsm_uom", "finished_uom",
        "finished_specification", "order_qty", "order_remarks", "is_subcontracted",
    )
    result = {field: original.get(field) for field in scalar_fields}
    returned_color = _get_returned_product_color(source.name) or original.color
    result.update({
        "original_flow_card": original_name,
        "color": returned_color,
        "production_qty": flt(source.total_weight),
        "grey_fabric_issues": [{
            "batch_no": source.return_batch_no,
            "grey_fabric_name": source.grey_fabric_name,
            "color": returned_color,
            "stock_roll_count": flt(source.total_roll_count),
            "stock_qty": flt(source.total_weight),
            "planned_roll_count": flt(source.total_roll_count),
            "planned_qty": flt(source.total_weight),
            "warehouse": source.target_warehouse,
        }],
        "process_requirements": _copy_child_rows(original.process_requirements, ("process_requirement", "process_requirement_name")),
        "packaging_requirements": _copy_child_rows(original.packaging_requirements, ("packaging_requirement", "packaging_requirement_name")),
        "operations": _copy_child_rows(original.operations, ("operation", "operation_code", "operation_name", "sequence_no")),
    })
    return result


def create_rework_flow_card_from_internal_transfer(transfer_name):
    source = frappe.get_doc("Finished Product to Grey Fabric", transfer_name)
    if source.docstatus != 1:
        frappe.throw(_("只能由已提交的成品库存转胚布仓单生成回修流转卡"))
    duplicate = frappe.db.get_value(
        "Production Flow Card",
        {"source_finished_product_to_grey_fabric": source.name, "docstatus": ["<", 2]},
        "name",
    )
    if duplicate:
        return duplicate

    original_name = (source.production_flow_card or "").rstrip("H")
    original = frappe.get_doc("Production Flow Card", original_name)
    scalar_fields = (
        "sales_order", "sales_order_item", "customer", "customer_order_no", "order_date",
        "delivery_date", "order_type", "process_type", "color_no", "color",
        "finished_product_name", "finished_width", "finished_gsm", "finished_gsm_uom", "finished_uom",
        "finished_specification", "order_qty", "order_remarks", "is_subcontracted",
    )
    card = frappe.new_doc("Production Flow Card")
    card.flow_card_type = "回修"
    card.source_finished_product_to_grey_fabric = source.name
    card.original_flow_card = original_name
    for field in scalar_fields:
        card.set(field, original.get(field))
    card.color_no = source.color_no or original.color_no
    card.color = source.color or original.color
    card.production_qty = flt(source.total_weight)
    card.production_requirements = _(
        "内部质量返修；来源转仓单：{0}；质量问题：{1}"
    ).format(source.name, source.quality_issue_type or "")
    card.append("grey_fabric_issues", {
        "batch_no": source.return_batch_no,
        "grey_fabric_name": source.grey_fabric_name,
        "color": source.color,
        "stock_roll_count": flt(source.total_roll_count),
        "stock_qty": flt(source.total_weight),
        "planned_roll_count": flt(source.total_roll_count),
        "planned_qty": flt(source.total_weight),
        "warehouse": source.target_warehouse,
    })
    for table_field, fields in (
        ("process_requirements", ("process_requirement", "process_requirement_name")),
        ("packaging_requirements", ("packaging_requirement", "packaging_requirement_name")),
        ("operations", ("operation", "operation_code", "operation_name", "sequence_no")),
    ):
        for values in _copy_child_rows(original.get(table_field), fields):
            card.append(table_field, values)
    card.insert(ignore_permissions=True)
    return card.name


def _get_returned_product_color(source_return_to_grey_fabric):
    colors = frappe.db.sql(
        """SELECT DISTINCT TRIM(product_return.color) AS color
        FROM `tabFinished Product Return to Grey Fabric Item` source_item
        INNER JOIN `tabFinished Product Return` product_return
            ON product_return.name = source_item.return_document
        WHERE source_item.parent = %(source)s
          AND product_return.docstatus = 1
          AND COALESCE(TRIM(product_return.color), '') != ''
        ORDER BY color""",
        {"source": source_return_to_grey_fabric},
        pluck=True,
    )
    if len(colors) > 1:
        frappe.throw(_("成品退货转胚布仓单包含多个颜色，不能生成同一张回修流转卡"))
    return colors[0] if colors else ""


@frappe.whitelist()
def get_available_rework_sources(doctype, txt, searchfield, start, page_len, filters, as_dict=False, **kwargs):
    rows = frappe.db.sql(
        """SELECT source.name, source.production_flow_card, source.return_batch_no,
                  source.customer_name, source.total_weight
           FROM `tabFinished Product Return to Grey Fabric` source
           LEFT JOIN `tabProduction Flow Card` card
             ON card.source_return_to_grey_fabric = source.name AND card.docstatus < 2
           WHERE source.docstatus = 1 AND card.name IS NULL
             AND (source.name LIKE %(txt)s OR source.production_flow_card LIKE %(txt)s
                  OR source.return_batch_no LIKE %(txt)s OR source.customer_name LIKE %(txt)s)
           ORDER BY source.transfer_date DESC, source.modified DESC
           LIMIT %(start)s, %(page_len)s""",
        {"txt": f"%{txt}%", "start": int(start), "page_len": int(page_len)},
        as_dict=True,
    )
    if as_dict:
        return [{
            "name": row.name, "原生产流转卡": row.production_flow_card,
            "返修胚布批次": row.return_batch_no, "客户名称": row.customer_name,
            "可回修重量(Kg)": row.total_weight,
        } for row in rows]
    return [[row.name, row.production_flow_card, row.return_batch_no, row.customer_name, row.total_weight] for row in rows]


@frappe.whitelist()
def get_available_rework_flow_cards(doctype, txt, searchfield, start, page_len, filters, as_dict=False, **kwargs):
    rows = frappe.db.sql(
        """SELECT TRIM(TRAILING 'H' FROM source.production_flow_card) AS name,
                  MAX(source.customer_name) AS customer_name,
                  COUNT(DISTINCT source.name) AS source_count,
                  SUM(source.total_weight) AS available_weight
           FROM `tabFinished Product Return to Grey Fabric` source
           LEFT JOIN `tabProduction Flow Card` card
             ON card.source_return_to_grey_fabric = source.name AND card.docstatus < 2
           WHERE source.docstatus = 1 AND card.name IS NULL
             AND (source.production_flow_card LIKE %(txt)s OR source.customer_name LIKE %(txt)s)
           GROUP BY TRIM(TRAILING 'H' FROM source.production_flow_card)
           ORDER BY MAX(source.modified) DESC
           LIMIT %(start)s, %(page_len)s""",
        {"txt": f"%{txt}%", "start": int(start), "page_len": int(page_len)},
        as_dict=True,
    )
    if as_dict:
        return [{
            "name": row.name, "客户名称": row.customer_name,
            "可用转胚布单数": row.source_count, "可回修重量(Kg)": row.available_weight,
        } for row in rows]
    return [[row.name, row.customer_name, row.source_count, row.available_weight] for row in rows]


@frappe.whitelist()
def get_rework_sources_for_flow_card(original_flow_card):
    rows = frappe.db.sql(
        """SELECT source.name, source.return_batch_no, source.total_roll_count,
                  source.total_weight, source.total_yard_qty
           FROM `tabFinished Product Return to Grey Fabric` source
           LEFT JOIN `tabProduction Flow Card` card
             ON card.source_return_to_grey_fabric = source.name AND card.docstatus < 2
           WHERE source.docstatus = 1 AND card.name IS NULL
             AND TRIM(TRAILING 'H' FROM source.production_flow_card) = %(flow_card)s
           ORDER BY source.transfer_date, source.modified""",
        {"flow_card": original_flow_card}, as_dict=True,
    )
    if not rows:
        frappe.throw(_("该原始生产流转卡没有可用的已提交退货转胚布仓单"))
    return rows


def _copy_child_rows(rows, fields):
    return [{field: row.get(field) for field in fields} for row in (rows or [])]


def _get_submitted_downstream_documents(flow_card):
    documents = []
    for doctype in ("Grey Fabric Issue", "Site Dyeing Material Sheet", "Finished Product Packing Receipt", "Finished Product Delivery"):
        documents.extend((doctype, row.name) for row in frappe.get_all(
            doctype,
            filters={"flow_card" if doctype == "Grey Fabric Issue" else "production_flow_card": flow_card, "docstatus": 1},
            fields=["name"],
        ))
    return documents


def _get_active_material_sheets(flow_card):
    return frappe.get_all(
        "Site Dyeing Material Sheet",
        filters={"production_flow_card": flow_card, "docstatus": 1},
        fields=["name", "material_sheet_status"],
        order_by="modified desc",
    )


@frappe.whitelist()
def close_production_flow_card(flow_card, closure_reason, closure_remarks=None):
    card = frappe.get_doc("Production Flow Card", flow_card)
    card.check_permission("write")
    if card.docstatus != 1:
        frappe.throw(_("只有已提交的生产流转卡才能关闭生产"))
    if (card.production_status or "进行中") == "已关闭":
        frappe.throw(_("生产流转卡已经关闭"))
    valid_reasons = {"客户取消", "质量异常", "胚布不足", "计划调整", "其他"}
    if closure_reason not in valid_reasons:
        frappe.throw(_("请选择关闭原因"))
    active_sheets = _get_active_material_sheets(card.name)
    if active_sheets:
        names = "、".join(row.name for row in active_sheets)
        frappe.throw(_("仍有已提交的现场染色料单 {0}，请先完成、退料或取消后再关闭生产").format(names))

    closed_at = now_datetime()
    frappe.db.set_value(
        "Production Flow Card",
        card.name,
        {
            "production_status": "已关闭",
            "closure_date": closed_at,
            "closure_reason": closure_reason,
            "closure_remarks": (closure_remarks or "").strip(),
            "closed_by": frappe.session.user,
        },
        update_modified=False,
    )
    record_production_progress(
        card.name,
        "生产关闭",
        "生产已关闭",
        "Production Flow Card",
        card.name,
        description="关闭原因：{0}{1}".format(closure_reason, "；" + (closure_remarks or "").strip() if (closure_remarks or "").strip() else ""),
    )
    frappe.get_doc("Production Flow Card", card.name).add_comment(
        "Info", _("已关闭生产。原因：{0}").format(closure_reason)
    )
    return {"production_status": "已关闭", "closure_date": closed_at}


@frappe.whitelist()
def reopen_production_flow_card(flow_card):
    card = frappe.get_doc("Production Flow Card", flow_card)
    card.check_permission("write")
    if card.docstatus != 1:
        frappe.throw(_("只有已提交的生产流转卡才能重新开启生产"))
    if (card.production_status or "进行中") != "已关闭":
        frappe.throw(_("当前生产流转卡未处于已关闭状态"))

    frappe.db.set_value(
        "Production Flow Card",
        card.name,
        {
            "production_status": "进行中",
            "closure_date": None,
            "closure_reason": "",
            "closure_remarks": "",
            "closed_by": "",
        },
        update_modified=False,
    )
    record_production_progress(
        card.name,
        "生产关闭",
        "生产已重新开启",
        "Production Flow Card",
        card.name,
        description="生产已重新开启",
    )
    frappe.get_doc("Production Flow Card", card.name).add_comment("Info", _("已重新开启生产"))
    return {"production_status": "进行中"}


def _batch_stock_query(customer=None, order_type=None, batch_no=None, location=None):
    customer_condition = (
        "COALESCE(receipt.customer, return_source.customer, internal_source.customer, '') = %(customer)s"
        if order_type == "来料加工"
        else "COALESCE(receipt.customer, '') = '' AND (return_source.customer IS NULL OR return_source.customer = %(customer)s) AND (internal_source.customer IS NULL OR internal_source.customer = %(customer)s)"
    )
    batch_condition = "AND stock.batch_no = %(batch_no)s" if batch_no else ""
    location_condition = "AND stock.location = %(location)s" if location else ""
    return frappe.db.sql(
        f"""
        SELECT stock.batch_no, stock.item_code, stock.item_name AS grey_fabric_name, stock.color,
            COALESCE(master.specification, '') AS specification, stock.stock_roll_count, stock.stock_qty, stock.location AS warehouse,
            stock.location
        FROM (
            SELECT COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no) AS batch_no,
                sle.item_code, MAX(item.item_name) AS item_name,
                MAX(receipt_item.color) AS color,
                GREATEST(
                    COALESCE(MAX(receipt_rolls.stock_roll_count), MAX(return_transfer.total_roll_count), MAX(internal_transfer.total_roll_count), 0)
                    - COALESCE(MAX(issued_rolls.issue_roll_count), 0),
                    0
                ) AS stock_roll_count,
                SUM(sle.actual_qty) AS stock_qty,
                sle.warehouse AS location
            FROM `tabStock Ledger Entry` sle
            INNER JOIN `tabItem` item ON item.name = sle.item_code
            LEFT JOIN `tabSerial and Batch Entry` bundle_entry ON bundle_entry.parent = sle.serial_and_batch_bundle
            LEFT JOIN `tabCustomer Grey Fabric Receipt Item` receipt_item
                ON receipt_item.batch_no = COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no)
            LEFT JOIN `tabCustomer Grey Fabric Receipt` receipt
                ON receipt.name = receipt_item.parent AND receipt.docstatus = 1
            LEFT JOIN `tabFinished Product Return to Grey Fabric` return_transfer
                ON return_transfer.return_batch_no = COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no)
                AND return_transfer.docstatus = 1
            LEFT JOIN `tabFinished Product to Grey Fabric` internal_transfer
                ON internal_transfer.return_batch_no = COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no)
                AND internal_transfer.docstatus = 1
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
                    WHERE lft >= (SELECT lft FROM `tabItem Group` WHERE name = %(grey_group)s)
                    AND rgt <= (SELECT rgt FROM `tabItem Group` WHERE name = %(grey_group)s)
                )
            GROUP BY COALESCE(NULLIF(sle.batch_no, ''), bundle_entry.batch_no), sle.item_code, sle.warehouse
            HAVING SUM(sle.actual_qty) > 0
        ) stock
        LEFT JOIN `tabGrey Fabric Master` master ON master.name = stock.item_code
        LEFT JOIN `tabCustomer Grey Fabric Receipt Item` receipt_item ON receipt_item.batch_no = stock.batch_no
        LEFT JOIN `tabCustomer Grey Fabric Receipt` receipt ON receipt.name = receipt_item.parent AND receipt.docstatus = 1
        LEFT JOIN `tabFinished Product Return to Grey Fabric` return_source
            ON return_source.return_batch_no = stock.batch_no AND return_source.docstatus = 1
        LEFT JOIN `tabFinished Product to Grey Fabric` internal_source
            ON internal_source.return_batch_no = stock.batch_no AND internal_source.docstatus = 1
        WHERE {customer_condition} {batch_condition} {location_condition}
        ORDER BY stock.batch_no, stock.stock_qty DESC
        """,
        {"customer": customer or "", "batch_no": batch_no or "", "location": location or "", "grey_group": get_setting("grey_fabric_item_group")},
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
        """SELECT name, grey_fabric_batch, item_name, color_no
        FROM `tabDyeing Sales Order Item`
        WHERE parent = %(sales_order)s
          AND parenttype = 'Dyeing Sales Order'
          AND (name LIKE %(txt)s OR grey_fabric_batch LIKE %(txt)s OR item_name LIKE %(txt)s OR color_no LIKE %(txt)s)
        ORDER BY idx LIMIT %(page_len)s OFFSET %(start)s""",
        {"sales_order": sales_order, "txt": f"%{txt}%", "page_len": page_len, "start": start},
    )


@frappe.whitelist()
def get_dyeing_sales_order_items(sales_order):
    """选择染整销售订单后，返回该订单可用的明细。"""
    order = frappe.get_doc("Dyeing Sales Order", sales_order)
    order.check_permission("read")
    if order.docstatus != 1:
        frappe.throw(_("只能引用已提交的染整销售订单"))
    return [
        {
            "name": row.name,
            "grey_fabric_batch": row.grey_fabric_batch,
            "item_code": row.item_code,
            "item_name": row.item_name,
            "color_no": row.color_no,
            "color": row.color,
            "qty": row.qty,
            "uom": row.uom,
        }
        for row in order.items
    ]


@frappe.whitelist()
def get_sales_order_item_details(sales_order, sales_order_item):
    order = frappe.get_doc("Dyeing Sales Order", sales_order)
    item = next((row for row in order.items if row.name == sales_order_item), None)
    if not item:
        frappe.throw(_("染整销售订单明细不属于当前染整销售订单"))
    return {
        "customer": order.customer,
        "customer_order_no": order.customer_order_no or "",
        "order_date": order.transaction_date,
        "delivery_date": order.delivery_date,
        "order_type": order.order_type or "",
        "process_type": item.process_type or "",
        "color_no": item.color_no or "",
        "color": item.color or "",
        "finished_product_name": item.finished_product_name or item.item_name or "",
        "finished_width": item.finished_width or "",
        "finished_gsm": item.finished_gsm or "",
        "finished_gsm_uom": item.finished_gsm_uom or "g/㎡",
        "finished_uom": item.uom or "",
        "finished_specification": item.finished_specification or "",
        "order_qty": item.qty or 0,
        "production_qty": item.qty or 0,
        "order_remarks": item.order_remark or order.order_remark or "",
        "process_requirements": [
            {"process_requirement": row.process_requirement, "process_requirement_name": row.process_requirement_name}
            for row in (order.process_requirements or [])
        ],
        "packaging_requirements": [
            {"packaging_requirement": row.packaging_requirement, "packaging_requirement_name": row.packaging_requirement_name}
            for row in (order.packaging_requirements or [])
        ],
    }


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_process_requirements_for_selection(doctype, txt, searchfield, start, page_len, filters, as_dict=False, **kwargs):
    excluded_condition, params = _selection_exclusion(filters)
    params.update({"txt": f"%{txt}%", "page_len": page_len, "start": start})
    return frappe.db.sql(
        """SELECT name, process_requirement_code, process_requirement_name
        FROM `tabProcess Requirement`
        WHERE disabled = 0
          {excluded_condition}
          AND (
              name LIKE %(txt)s
              OR process_requirement_code LIKE %(txt)s
              OR process_requirement_name LIKE %(txt)s
          )
        ORDER BY process_requirement_code
        LIMIT %(page_len)s OFFSET %(start)s""".format(excluded_condition=excluded_condition),
        params,
        as_dict=as_dict,
    )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_packaging_requirements_for_selection(doctype, txt, searchfield, start, page_len, filters, as_dict=False, **kwargs):
    excluded_condition, params = _selection_exclusion(filters)
    params.update({"txt": f"%{txt}%", "page_len": page_len, "start": start})
    return frappe.db.sql(
        """SELECT name, packaging_requirement_code, packaging_requirement_name
        FROM `tabPackaging Requirement`
        WHERE disabled = 0
          {excluded_condition}
          AND (
              name LIKE %(txt)s
              OR packaging_requirement_code LIKE %(txt)s
              OR packaging_requirement_name LIKE %(txt)s
          )
        ORDER BY packaging_requirement_code
        LIMIT %(page_len)s OFFSET %(start)s""".format(excluded_condition=excluded_condition),
        params,
        as_dict=as_dict,
    )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_production_operations_for_selection(doctype, txt, searchfield, start, page_len, filters, as_dict=False, **kwargs):
    excluded_condition, params = _selection_exclusion(filters)
    params.update({"txt": f"%{txt}%", "page_len": page_len, "start": start})
    return frappe.db.sql(
        """SELECT name, production_operation_code, production_operation_name, sequence_no
        FROM `tabProduction Operation`
        WHERE disabled = 0
          AND COALESCE(sequence_no, '') != ''
          {excluded_condition}
          AND (
              name LIKE %(txt)s
              OR production_operation_code LIKE %(txt)s
              OR production_operation_name LIKE %(txt)s
          )
        ORDER BY CAST(NULLIF(sequence_no, '') AS UNSIGNED), production_operation_code
        LIMIT %(page_len)s OFFSET %(start)s""".format(excluded_condition=excluded_condition),
        params,
        as_dict=as_dict,
    )


def _selection_exclusion(filters):
    filters = frappe.parse_json(filters) or {}
    excluded = frappe.parse_json(filters.get("excluded_names") or "[]") or []
    excluded = list(dict.fromkeys(value for value in excluded if value))
    if not excluded:
        return "", {}
    placeholders = ", ".join(f"%(excluded_{index})s" for index in range(len(excluded)))
    return (
        f"AND name NOT IN ({placeholders})",
        {f"excluded_{index}": value for index, value in enumerate(excluded)},
    )

def record_production_progress(flow_card, operation, progress_status, source_doctype, source_document,
                               batch_no="", quantity=0, uom="", production_resource="",
                               material_sheet_type="", dyeing_sequence=0, description="",
                               roll_count=0, yard_qty=0):
    if not flow_card:
        return
    operation = (
        frappe.db.get_value("Production Operation", operation, "production_operation_name")
        if operation and frappe.db.exists("Production Operation", operation)
        else operation
    )
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
        "roll_count": roll_count,
        "quantity": flt(quantity),
        "uom": uom,
        "yard_qty": flt(yard_qty),
        "production_resource": production_resource,
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
