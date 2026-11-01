from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from dyeing_finishing.dyeing_finishing.settings import get_setting


TOLERANCE = 0.000001


def execute(filters=None):
    filters = _normalize_filters(filters)
    context = _get_context(filters)
    opening = _get_opening(filters, context)
    movements = _get_movements(filters, context)
    movements.extend(_get_inventory_count_movements(filters, context))

    batches = {key[3] for key in opening} | {row.batch_no for row in movements}
    ownership = _get_batch_ownership(batches)
    _apply_roll_deltas(movements)
    _apply_business_details(movements, ownership)
    data, report_summary = _build_rows(filters, opening, movements, ownership)
    return _get_columns(), data, None, None, report_summary


def _normalize_filters(filters):
    filters = frappe._dict(filters or {})
    filters.from_date = getdate(filters.from_date or nowdate())
    filters.to_date = getdate(filters.to_date or nowdate())
    if filters.from_date > filters.to_date:
        frappe.throw(_("开始日期不能晚于结束日期。"))
    filters.include_child_warehouses = cint(filters.include_child_warehouses)
    # Frappe omits unchecked Check filters from the request. Treat an omitted
    # value as unchecked so the UI toggle can actually hide those rows.
    filters.show_opening = cint(filters.show_opening)
    filters.show_zero_balance = cint(filters.show_zero_balance)
    filters.group_by = filters.group_by or "客户+匹号+仓库"
    filters.sort_order = filters.sort_order or "记账顺序"
    return filters


def _get_context(filters):
    grey_group = get_setting("grey_fabric_item_group")
    if not grey_group or not frappe.db.exists("Item Group", grey_group):
        frappe.throw(_("请先在印染系统设置中配置胚布物料组。"))
    warehouses = []
    if filters.warehouse:
        warehouse = frappe.db.get_value("Warehouse", filters.warehouse, ["lft", "rgt", "company"], as_dict=True)
        if not warehouse:
            frappe.throw(_("仓库 {0} 不存在。").format(filters.warehouse))
        if filters.company and warehouse.company != filters.company:
            frappe.throw(_("所选仓库不属于公司 {0}。").format(filters.company))
        if filters.include_child_warehouses:
            warehouses = frappe.get_all("Warehouse", filters={"lft": [">=", warehouse.lft], "rgt": ["<=", warehouse.rgt]}, pluck="name")
        else:
            warehouses = [filters.warehouse]
    return frappe._dict(grey_group=grey_group, warehouses=tuple(warehouses))


def _base_conditions(filters, context, date_condition):
    batch_expression = (
        "COALESCE(NULLIF(sle.batch_no, ''), (SELECT sbe.batch_no FROM `tabSerial and Batch Entry` sbe "
        "WHERE sbe.parent = sle.serial_and_batch_bundle LIMIT 1))"
    )
    conditions = ["sle.is_cancelled = 0", date_condition, f"{batch_expression} IS NOT NULL", f"{batch_expression} != ''"]
    values = {"from_date": filters.from_date, "to_date": filters.to_date, "grey_group": context.grey_group}
    if filters.company:
        conditions.append("sle.company = %(company)s")
        values["company"] = filters.company
    if context.warehouses:
        conditions.append("sle.warehouse IN %(warehouses)s")
        values["warehouses"] = context.warehouses
    if filters.item_code:
        conditions.append("sle.item_code = %(item_code)s")
        values["item_code"] = filters.item_code
    if filters.batch_no:
        conditions.append(f"{batch_expression} = %(batch_no)s")
        values["batch_no"] = filters.batch_no
    return conditions, values


def _get_opening(filters, context):
    opening = defaultdict(lambda: frappe._dict(qty=0.0, rolls=0.0, stock_uom=""))
    conditions, values = _base_conditions(filters, context, "sle.posting_date < %(from_date)s")
    weight_rows = frappe.db.sql(
        f"""
        SELECT sle.company, sle.warehouse, sle.item_code,
            COALESCE(NULLIF(sle.batch_no, ''), (SELECT sbe.batch_no FROM `tabSerial and Batch Entry` sbe
                WHERE sbe.parent = sle.serial_and_batch_bundle LIMIT 1)) AS batch_no,
            MAX(item.stock_uom) AS stock_uom, SUM(sle.actual_qty) AS qty
        FROM `tabStock Ledger Entry` sle
        INNER JOIN `tabItem` item ON item.name = sle.item_code
        WHERE {' AND '.join(conditions)}
          AND item.item_group IN (
            SELECT name FROM `tabItem Group`
            WHERE lft >= (SELECT lft FROM `tabItem Group` WHERE name = %(grey_group)s)
              AND rgt <= (SELECT rgt FROM `tabItem Group` WHERE name = %(grey_group)s)
          )
        GROUP BY sle.company, sle.warehouse, sle.item_code,
            COALESCE(NULLIF(sle.batch_no, ''), (SELECT sbe.batch_no FROM `tabSerial and Batch Entry` sbe
                WHERE sbe.parent = sle.serial_and_batch_bundle LIMIT 1))
        """, values, as_dict=True,
    )
    for row in weight_rows:
        key = _key(row)
        opening[key].qty += flt(row.qty)
        opening[key].stock_uom = row.stock_uom
    for row in _get_opening_roll_rows(filters, context):
        key = _key(row)
        opening[key].rolls += flt(row.roll_delta)
        opening[key].stock_uom = opening[key].stock_uom or row.stock_uom
    return opening


def _non_sle_conditions(filters, context, date_condition, prefix=""):
    conditions = [date_condition, f"{prefix}batch_no IS NOT NULL", f"{prefix}batch_no != ''"]
    values = {"from_date": filters.from_date, "to_date": filters.to_date, "grey_group": context.grey_group}
    if filters.company:
        conditions.append(f"{prefix}company = %(company)s")
        values["company"] = filters.company
    if context.warehouses:
        conditions.append(f"{prefix}warehouse IN %(warehouses)s")
        values["warehouses"] = context.warehouses
    if filters.item_code:
        conditions.append(f"{prefix}item_code = %(item_code)s")
        values["item_code"] = filters.item_code
    if filters.batch_no:
        conditions.append(f"{prefix}batch_no = %(batch_no)s")
        values["batch_no"] = filters.batch_no
    return " AND ".join(conditions), values


def _get_opening_roll_rows(filters, context):
    common, values = _non_sle_conditions(
        filters, context, "roll_event.posting_date < %(from_date)s", "roll_event."
    )
    return frappe.db.sql(
        f"""
        SELECT roll_event.company, roll_event.warehouse, roll_event.item_code, roll_event.batch_no,
            MAX(roll_event.stock_uom) stock_uom, SUM(roll_event.roll_delta) roll_delta
        FROM (
            SELECT receipt_warehouse.company, COALESCE(NULLIF(item.target_location, ''), receipt.target_warehouse) warehouse,
                item.item_code, item.batch_no, product.stock_uom, item.roll_count roll_delta,
                receipt.receipt_date posting_date
            FROM `tabCustomer Grey Fabric Receipt Item` item
            INNER JOIN `tabCustomer Grey Fabric Receipt` receipt ON receipt.name = item.parent AND receipt.docstatus = 1
            INNER JOIN `tabItem` product ON product.name = item.item_code
            INNER JOIN `tabWarehouse` receipt_warehouse
                ON receipt_warehouse.name = COALESCE(NULLIF(item.target_location, ''), receipt.target_warehouse)
            WHERE item.batch_no IS NOT NULL AND item.batch_no != ''
            UNION ALL
            SELECT entry.company, detail.t_warehouse, detail.item_code, detail.batch_no,
                product.stock_uom, COALESCE(detail.custom_roll_count, 0), entry.posting_date
            FROM `tabStock Entry Detail` detail
            INNER JOIN `tabStock Entry` entry ON entry.name = detail.parent AND entry.docstatus = 1
            INNER JOIN `tabItem` product ON product.name = detail.item_code
            WHERE COALESCE(detail.t_warehouse, '') != '' AND COALESCE(detail.custom_roll_count, 0) != 0
              AND NOT EXISTS (
                SELECT 1 FROM `tabCustomer Grey Fabric Receipt` receipt
                WHERE receipt.stock_entry = entry.name AND receipt.docstatus = 1
              )
            UNION ALL
            SELECT entry.company, detail.s_warehouse, detail.item_code, detail.batch_no,
                product.stock_uom, -COALESCE(detail.custom_roll_count, 0), entry.posting_date
            FROM `tabStock Entry Detail` detail
            INNER JOIN `tabStock Entry` entry ON entry.name = detail.parent AND entry.docstatus = 1
            INNER JOIN `tabItem` product ON product.name = detail.item_code
            WHERE COALESCE(detail.s_warehouse, '') != '' AND COALESCE(detail.custom_roll_count, 0) != 0
            UNION ALL
            SELECT warehouse.company, item.stock_warehouse, item.item_code, item.batch_no,
                item.stock_uom, item.difference_roll_count, count.count_date
            FROM `tabGrey Fabric Inventory Count Item` item
            INNER JOIN `tabGrey Fabric Inventory Count` count ON count.name = item.parent
                AND count.docstatus = 1 AND count.status = '已审核'
            INNER JOIN `tabWarehouse` warehouse ON warehouse.name = item.stock_warehouse
            WHERE COALESCE(item.difference_roll_count, 0) != 0
        ) roll_event
        INNER JOIN `tabItem` item_group_filter ON item_group_filter.name = roll_event.item_code
        WHERE {common}
          AND item_group_filter.item_group IN (
            SELECT name FROM `tabItem Group`
            WHERE lft >= (SELECT lft FROM `tabItem Group` WHERE name = %(grey_group)s)
              AND rgt <= (SELECT rgt FROM `tabItem Group` WHERE name = %(grey_group)s)
          )
        GROUP BY roll_event.company, roll_event.warehouse, roll_event.item_code, roll_event.batch_no
        """, values, as_dict=True,
    )


def _get_movements(filters, context):
    conditions, values = _base_conditions(filters, context, "sle.posting_date BETWEEN %(from_date)s AND %(to_date)s")
    return frappe.db.sql(
        f"""
        SELECT sle.name AS ledger_entry, sle.company, sle.posting_date, sle.posting_time,
            sle.creation, sle.owner AS created_by, sle.item_code, item.item_name, item.stock_uom,
            sle.warehouse, sle.actual_qty, sle.voucher_type, sle.voucher_no, sle.voucher_detail_no,
            COALESCE(NULLIF(sle.batch_no, ''), (SELECT sbe.batch_no FROM `tabSerial and Batch Entry` sbe
                WHERE sbe.parent = sle.serial_and_batch_bundle LIMIT 1)) AS batch_no,
            detail.s_warehouse, detail.t_warehouse, COALESCE(detail.custom_roll_count, 0) AS detail_roll_count,
            detail.custom_grey_fabric_issue, detail.custom_production_flow_card,
            detail.custom_grey_fabric_customer_transfer, detail.custom_customer_grey_fabric_return,
            detail.custom_grey_fabric_loss,
            detail.custom_finished_product_return_to_grey_fabric, detail.custom_finished_product_to_grey_fabric,
            entry.stock_entry_type, entry.remarks
        FROM `tabStock Ledger Entry` sle
        INNER JOIN `tabItem` item ON item.name = sle.item_code
        LEFT JOIN `tabStock Entry Detail` detail ON detail.name = sle.voucher_detail_no
        LEFT JOIN `tabStock Entry` entry ON entry.name = sle.voucher_no AND sle.voucher_type = 'Stock Entry'
        WHERE {' AND '.join(conditions)}
          AND NOT (
            sle.voucher_type = 'Stock Reconciliation'
            AND EXISTS (
              SELECT 1 FROM `tabGrey Fabric Inventory Count` inventory
              WHERE inventory.stock_reconciliation = sle.voucher_no
                AND inventory.docstatus = 1 AND inventory.status = '已审核'
            )
          )
          AND item.item_group IN (
            SELECT name FROM `tabItem Group`
            WHERE lft >= (SELECT lft FROM `tabItem Group` WHERE name = %(grey_group)s)
              AND rgt <= (SELECT rgt FROM `tabItem Group` WHERE name = %(grey_group)s)
          )
        ORDER BY sle.posting_date, sle.posting_time, sle.creation, sle.name
        """, values, as_dict=True,
    )


def _get_inventory_count_movements(filters, context):
    conditions = ["inventory.count_date BETWEEN %(from_date)s AND %(to_date)s"]
    values = {"from_date": filters.from_date, "to_date": filters.to_date, "grey_group": context.grey_group}
    if filters.company:
        conditions.append("warehouse.company = %(company)s")
        values["company"] = filters.company
    if context.warehouses:
        conditions.append("item.stock_warehouse IN %(warehouses)s")
        values["warehouses"] = context.warehouses
    if filters.item_code:
        conditions.append("item.item_code = %(item_code)s")
        values["item_code"] = filters.item_code
    if filters.batch_no:
        conditions.append("item.batch_no = %(batch_no)s")
        values["batch_no"] = filters.batch_no
    return frappe.db.sql(
        f"""
        SELECT CONCAT('COUNT-', inventory.name, '-', item.name) AS ledger_entry,
            warehouse.company, inventory.count_date AS posting_date, inventory.posting_time,
            inventory.modified AS creation, COALESCE(inventory.reviewed_by, inventory.owner) AS created_by,
            item.item_code, product.item_name, item.stock_uom, item.stock_warehouse AS warehouse,
            item.difference_qty AS actual_qty,
            CASE WHEN COALESCE(inventory.stock_reconciliation, '') != ''
                THEN 'Stock Reconciliation' ELSE 'Grey Fabric Inventory Count' END AS voucher_type,
            COALESCE(NULLIF(inventory.stock_reconciliation, ''), inventory.name) AS voucher_no,
            item.name AS voucher_detail_no, item.batch_no,
            item.stock_warehouse AS s_warehouse, item.stock_warehouse AS t_warehouse,
            item.difference_roll_count AS roll_delta, inventory.name AS inventory_count,
            item.difference_reason, inventory.remarks
        FROM `tabGrey Fabric Inventory Count Item` item
        INNER JOIN `tabGrey Fabric Inventory Count` inventory ON inventory.name = item.parent
            AND inventory.docstatus = 1 AND inventory.status = '已审核'
        INNER JOIN `tabWarehouse` warehouse ON warehouse.name = item.stock_warehouse
        INNER JOIN `tabItem` product ON product.name = item.item_code
        WHERE (
            ABS(COALESCE(item.difference_roll_count, 0)) > {TOLERANCE}
            OR ABS(COALESCE(item.difference_qty, 0)) > {TOLERANCE}
          )
          AND product.item_group IN (
            SELECT name FROM `tabItem Group`
            WHERE lft >= (SELECT lft FROM `tabItem Group` WHERE name = %(grey_group)s)
              AND rgt <= (SELECT rgt FROM `tabItem Group` WHERE name = %(grey_group)s)
          )
          AND {' AND '.join(conditions)}
        ORDER BY inventory.count_date, inventory.posting_time, inventory.modified, item.idx
        """, values, as_dict=True,
    )


def _apply_roll_deltas(movements):
    stock_entries = {row.voucher_no for row in movements if row.voucher_type == "Stock Entry"}
    reconciliations = {row.voucher_no for row in movements if row.voucher_type == "Stock Reconciliation"}
    receipt_rolls = {}
    if stock_entries:
        rows = frappe.db.sql(
            """
            SELECT receipt.stock_entry, item.batch_no, item.item_code,
                COALESCE(NULLIF(item.target_location, ''), receipt.target_warehouse) warehouse,
                item.roll_count
            FROM `tabCustomer Grey Fabric Receipt Item` item
            INNER JOIN `tabCustomer Grey Fabric Receipt` receipt ON receipt.name = item.parent AND receipt.docstatus = 1
            WHERE receipt.stock_entry IN %(stock_entries)s
            """, {"stock_entries": tuple(stock_entries)}, as_dict=True,
        )
        for row in rows:
            receipt_rolls[(row.stock_entry, row.batch_no, row.item_code, row.warehouse)] = flt(row.roll_count)

    count_rolls = {}
    if reconciliations:
        rows = frappe.db.sql(
            """
            SELECT count.stock_reconciliation, item.batch_no, item.item_code, item.stock_warehouse,
                item.difference_roll_count, item.difference_reason, count.name inventory_count
            FROM `tabGrey Fabric Inventory Count Item` item
            INNER JOIN `tabGrey Fabric Inventory Count` count ON count.name = item.parent
                AND count.docstatus = 1 AND count.status = '已审核'
            WHERE count.stock_reconciliation IN %(reconciliations)s
            """, {"reconciliations": tuple(reconciliations)}, as_dict=True,
        )
        for row in rows:
            count_rolls[(row.stock_reconciliation, row.batch_no, row.item_code, row.stock_warehouse)] = row

    for row in movements:
        if row.get("roll_delta") is not None:
            continue
        row.roll_delta = 0.0
        if row.voucher_type == "Stock Entry":
            receipt_roll = receipt_rolls.get((row.voucher_no, row.batch_no, row.item_code, row.warehouse))
            if receipt_roll is not None:
                row.roll_delta = receipt_roll
            elif flt(row.detail_roll_count):
                row.roll_delta = abs(flt(row.detail_roll_count)) if flt(row.actual_qty) >= 0 else -abs(flt(row.detail_roll_count))
        elif row.voucher_type == "Stock Reconciliation":
            count_row = count_rolls.get((row.voucher_no, row.batch_no, row.item_code, row.warehouse))
            if count_row:
                row.roll_delta = flt(count_row.difference_roll_count)
                row.inventory_count = count_row.inventory_count
                row.difference_reason = count_row.difference_reason


def _apply_business_details(movements, ownership):
    stock_entries = {row.voucher_no for row in movements if row.voucher_type == "Stock Entry"}
    receipt_docs = {}
    if stock_entries:
        receipt_docs = {
            row.stock_entry: row.name
            for row in frappe.get_all("Customer Grey Fabric Receipt",
                filters={"docstatus": 1, "stock_entry": ["in", list(stock_entries)]}, fields=["name", "stock_entry"])
        }

    transfer_names = {row.custom_grey_fabric_customer_transfer for row in movements if row.get("custom_grey_fabric_customer_transfer")}
    transfer_batches = {}
    if transfer_names:
        rows = frappe.get_all("Grey Fabric Customer Transfer Item",
            filters={"parent": ["in", list(transfer_names)]}, fields=["parent", "source_batch_no", "target_batch_no"])
        for row in rows:
            transfer_batches[(row.parent, row.source_batch_no)] = (row.source_batch_no, row.target_batch_no, "发出")
            transfer_batches[(row.parent, row.target_batch_no)] = (row.source_batch_no, row.target_batch_no, "收入")

    reconciliation_names = {row.voucher_no for row in movements if row.voucher_type == "Stock Reconciliation"}
    reconciliation_docs = {}
    if reconciliation_names:
        reconciliation_docs = {
            row.stock_reconciliation: row.name
            for row in frappe.get_all("Grey Fabric Inventory Count",
                filters={"docstatus": 1, "stock_reconciliation": ["in", list(reconciliation_names)]},
                fields=["name", "stock_reconciliation"])
        }

    loss_names = {row.custom_grey_fabric_loss for row in movements if row.get("custom_grey_fabric_loss")}
    loss_docs = {
        row.name: row
        for row in frappe.get_all("Grey Fabric Loss", filters={"name": ["in", list(loss_names)]},
            fields=["name", "loss_type", "reason_details"])
    } if loss_names else {}

    for row in movements:
        owner = ownership.get(row.batch_no, frappe._dict())
        row.customer = owner.get("customer")
        row.customer_name = owner.get("customer_name")
        row.color = owner.get("color")
        row.width = owner.get("width")
        row.gsm = owner.get("gsm")
        row.source_batch_no = owner.get("source_batch_no")
        row.target_batch_no = ""
        row.production_flow_card = row.get("custom_production_flow_card") or owner.get("production_flow_card")
        row.business_doctype = row.voucher_type
        row.business_document = row.voucher_no
        row.business_type = "其他库存变动"
        row.movement_type = "收入" if flt(row.actual_qty) > 0 else "发出" if flt(row.actual_qty) < 0 else "其他"

        if receipt_docs.get(row.voucher_no):
            row.business_type, row.business_doctype = "客户胚布入库", "Customer Grey Fabric Receipt"
            row.business_document = receipt_docs[row.voucher_no]
        elif row.get("custom_grey_fabric_issue"):
            row.business_type, row.business_doctype = "胚布出库", "Grey Fabric Issue"
            row.business_document = row.custom_grey_fabric_issue
        elif row.get("custom_grey_fabric_customer_transfer"):
            row.business_type, row.business_doctype, row.movement_type = "胚布过户", "Grey Fabric Customer Transfer", "过户"
            row.business_document = row.custom_grey_fabric_customer_transfer
            transfer = transfer_batches.get((row.business_document, row.batch_no))
            if transfer:
                row.source_batch_no, row.target_batch_no, row.transfer_direction = transfer
        elif row.get("custom_customer_grey_fabric_return"):
            row.business_type, row.business_doctype = "客户胚布退货", "Customer Grey Fabric Return"
            row.business_document = row.custom_customer_grey_fabric_return
        elif row.get("custom_grey_fabric_loss"):
            row.business_type, row.business_doctype, row.movement_type = "胚布报损", "Grey Fabric Loss", "报损"
            row.business_document = row.custom_grey_fabric_loss
            loss = loss_docs.get(row.business_document)
            if loss:
                row.difference_reason = loss.loss_type
                row.remarks = loss.reason_details or row.remarks
        elif row.get("custom_finished_product_return_to_grey_fabric"):
            row.business_type, row.business_doctype = "成品退货转胚布", "Finished Product Return to Grey Fabric"
            row.business_document = row.custom_finished_product_return_to_grey_fabric
        elif row.get("custom_finished_product_to_grey_fabric"):
            row.business_type, row.business_doctype = "成品库存转胚布", "Finished Product to Grey Fabric"
            row.business_document = row.custom_finished_product_to_grey_fabric
        elif row.get("inventory_count") or reconciliation_docs.get(row.voucher_no):
            row.business_type, row.business_doctype, row.movement_type = "胚布盘点", "Grey Fabric Inventory Count", "盘点调整"
            row.business_document = row.get("inventory_count") or reconciliation_docs[row.voucher_no]
        elif row.voucher_type == "Stock Entry" and row.stock_entry_type == "Material Transfer":
            row.business_type = "仓库调拨"

        row.counterparty_warehouse = _get_counterparty_warehouse(row)


def _get_counterparty_warehouse(row):
    source = row.get("s_warehouse")
    target = row.get("t_warehouse")
    if source == row.warehouse and target and target != row.warehouse:
        return target
    if target == row.warehouse and source and source != row.warehouse:
        return source
    return ""


def _get_batch_ownership(batches):
    if not batches:
        return {}
    rows = frappe.db.sql(
        """
        SELECT item.batch_no, receipt.customer,
            COALESCE(NULLIF(receipt.customer_name, ''), customer.customer_name, receipt.customer) customer_name,
            item.color, item.width, item.gsm, NULL source_batch_no, NULL production_flow_card, 1 priority
        FROM `tabCustomer Grey Fabric Receipt Item` item
        INNER JOIN `tabCustomer Grey Fabric Receipt` receipt ON receipt.name = item.parent AND receipt.docstatus = 1
        LEFT JOIN `tabCustomer` customer ON customer.name = receipt.customer
        WHERE item.batch_no IN %(batches)s
        UNION ALL
        SELECT item.target_batch_no, transfer.target_customer,
            COALESCE(NULLIF(transfer.target_customer_name, ''), customer.customer_name, transfer.target_customer),
            item.color, NULL, NULL, item.source_batch_no, NULL, 2
        FROM `tabGrey Fabric Customer Transfer Item` item
        INNER JOIN `tabGrey Fabric Customer Transfer` transfer ON transfer.name = item.parent AND transfer.docstatus = 1
        LEFT JOIN `tabCustomer` customer ON customer.name = transfer.target_customer
        WHERE item.target_batch_no IN %(batches)s
        UNION ALL
        SELECT doc.return_batch_no, doc.customer,
            COALESCE(NULLIF(doc.customer_name, ''), customer.customer_name, doc.customer),
            card.color, NULL, NULL, NULL, doc.production_flow_card, 3
        FROM `tabFinished Product Return to Grey Fabric` doc
        LEFT JOIN `tabCustomer` customer ON customer.name = doc.customer
        LEFT JOIN `tabProduction Flow Card` card ON card.name = doc.production_flow_card
        WHERE doc.docstatus = 1 AND doc.return_batch_no IN %(batches)s
        UNION ALL
        SELECT doc.return_batch_no, doc.customer,
            COALESCE(NULLIF(doc.customer_name, ''), customer.customer_name, doc.customer),
            card.color, NULL, NULL, NULL, doc.production_flow_card, 3
        FROM `tabFinished Product to Grey Fabric` doc
        LEFT JOIN `tabCustomer` customer ON customer.name = doc.customer
        LEFT JOIN `tabProduction Flow Card` card ON card.name = doc.production_flow_card
        WHERE doc.docstatus = 1 AND doc.return_batch_no IN %(batches)s
        ORDER BY priority
        """, {"batches": tuple(batches)}, as_dict=True,
    )
    result = {}
    for row in rows:
        result[row.batch_no] = row
    for row in result.values():
        source = result.get(row.source_batch_no)
        if source:
            row.width = row.width or source.width
            row.gsm = row.gsm or source.gsm
            row.color = row.color or source.color
    return result


def _build_rows(filters, opening, movements, ownership):
    movements.sort(key=_sort_key)
    balances = defaultdict(lambda: frappe._dict(qty=0.0, rolls=0.0))
    keys = set(opening)
    item_names = {}
    for key, values in opening.items():
        balances[key].qty = flt(values.qty)
        balances[key].rolls = flt(values.rolls)

    event_rows = []
    for movement in movements:
        key = _key(movement)
        keys.add(key)
        item_names[movement.item_code] = movement.item_name
        balance = balances[key]
        balance.qty += flt(movement.actual_qty)
        balance.rolls += flt(movement.roll_delta)
        movement.balance_qty = balance.qty
        movement.balance_roll_count = balance.rolls
        event_rows.append(movement)

    allowed_keys = set()
    for key in keys:
        owner = ownership.get(key[3], frappe._dict())
        if filters.customer and owner.get("customer") != filters.customer:
            continue
        ending = balances[key]
        if not filters.show_zero_balance and abs(flt(ending.qty)) <= TOLERANCE and abs(flt(ending.rolls)) <= TOLERANCE:
            continue
        allowed_keys.add(key)

    missing_items = list({key[2] for key in allowed_keys if key[2] not in item_names})
    if missing_items:
        item_names.update(dict(frappe.get_all(
            "Item", filters={"name": ["in", missing_items]}, fields=["name", "item_name"], as_list=True,
        )))

    opening_rows = []
    if filters.show_opening:
        for key in sorted(allowed_keys, key=lambda value: (value[1], value[3], value[2])):
            values = opening.get(key, frappe._dict(qty=0, rolls=0, stock_uom=""))
            if abs(flt(values.qty)) <= TOLERANCE and abs(flt(values.rolls)) <= TOLERANCE:
                continue
            opening_rows.append(_make_opening_row(filters, [key], opening, ownership, item_names))

    visible_events = []
    summary_events = []
    for row in event_rows:
        if _key(row) not in allowed_keys:
            continue
        row.receipt_roll_count = max(flt(row.roll_delta), 0)
        row.issue_roll_count = max(-flt(row.roll_delta), 0)
        row.receipt_qty = max(flt(row.actual_qty), 0)
        row.issue_qty = max(-flt(row.actual_qty), 0)
        row.stock_voucher_type = row.voucher_type
        row.stock_voucher = row.voucher_no
        summary_events.append(row)
        if filters.movement_type and row.movement_type != filters.movement_type:
            continue
        if filters.business_type and row.business_type != filters.business_type:
            continue
        if filters.business_document and filters.business_document not in (row.business_document or ""):
            continue
        visible_events.append(row)

    report_summary = _get_report_summary(opening, balances, allowed_keys, summary_events)
    if filters.group_by != "不分组":
        data = _build_grouped_rows(
            filters, opening, balances, allowed_keys, visible_events, ownership, item_names,
        )
    else:
        if filters.sort_order == "最新优先":
            visible_events.reverse()
        data = opening_rows + visible_events
    return data, report_summary


def _build_grouped_rows(filters, opening, balances, allowed_keys, visible_events, ownership, item_names):
    group_keys = defaultdict(list)
    for key in allowed_keys:
        group_keys[_get_group_key(filters.group_by, key, ownership)].append(key)

    events_by_group = defaultdict(list)
    for row in visible_events:
        events_by_group[_get_group_key(filters.group_by, _key(row), ownership)].append(row)

    data = []
    for group in sorted(group_keys):
        keys = sorted(group_keys[group], key=lambda value: (value[1], value[3], value[2]))
        rows = events_by_group.get(group, [])
        if filters.show_opening:
            data.append(_make_opening_row(filters, keys, opening, ownership, item_names))
        if filters.sort_order == "最新优先":
            rows = list(reversed(rows))
        data.extend(rows)
        data.append(_make_subtotal_row(keys, rows, balances, ownership, item_names))
    return data


def _get_group_key(group_by, key, ownership):
    owner = ownership.get(key[3], frappe._dict())
    customer_name = owner.get("customer_name") or owner.get("customer") or _("未指定客户")
    customer = owner.get("customer") or ""
    if group_by == "仓库+匹号":
        return (key[1], key[3], customer_name, customer)
    return (customer_name, customer, key[3], key[1])


def _make_opening_row(filters, keys, opening, ownership, item_names):
    key = keys[0]
    owner = ownership.get(key[3], frappe._dict())
    opening_rolls = sum(flt(opening.get(item, {}).get("rolls")) for item in keys)
    opening_qty = sum(flt(opening.get(item, {}).get("qty")) for item in keys)
    stock_uom = next((opening.get(item, {}).get("stock_uom") for item in keys if opening.get(item, {}).get("stock_uom")), "")
    return frappe._dict(
        row_type="opening", posting_date=filters.from_date, posting_time="00:00:00",
        movement_type="期初", business_type="期初结存", company=key[0], warehouse=key[1],
        item_code=key[2], item_name=item_names.get(key[2]), batch_no=key[3],
        customer=owner.get("customer"), customer_name=owner.get("customer_name"),
        color=owner.get("color"), width=owner.get("width"), gsm=owner.get("gsm"),
        balance_roll_count=opening_rolls, balance_qty=opening_qty, stock_uom=stock_uom,
    )


def _make_subtotal_row(keys, rows, balances, ownership, item_names):
    key = keys[0]
    owner = ownership.get(key[3], frappe._dict())
    customer_name = owner.get("customer_name") or owner.get("customer") or _("未指定客户")
    return frappe._dict(
        row_type="subtotal", bold=1, movement_type="小计", business_type="本组小计",
        company=key[0], warehouse=key[1], item_code=key[2], item_name=item_names.get(key[2]),
        batch_no=key[3], customer=owner.get("customer"), customer_name=_('{0}【小计】').format(customer_name),
        color=owner.get("color"), width=owner.get("width"), gsm=owner.get("gsm"),
        receipt_roll_count=sum(flt(row.receipt_roll_count) for row in rows),
        issue_roll_count=sum(flt(row.issue_roll_count) for row in rows),
        balance_roll_count=sum(flt(balances[item].rolls) for item in keys),
        receipt_qty=sum(flt(row.receipt_qty) for row in rows),
        issue_qty=sum(flt(row.issue_qty) for row in rows),
        balance_qty=sum(flt(balances[item].qty) for item in keys),
        stock_uom=next((row.stock_uom for row in rows if row.stock_uom), ""),
    )


def _get_report_summary(opening, balances, allowed_keys, movements):
    opening_rolls = sum(flt(opening.get(key, {}).get("rolls")) for key in allowed_keys)
    opening_qty = sum(flt(opening.get(key, {}).get("qty")) for key in allowed_keys)
    receipt_rolls = sum(flt(row.receipt_roll_count) for row in movements)
    issue_rolls = sum(flt(row.issue_roll_count) for row in movements)
    receipt_qty = sum(flt(row.receipt_qty) for row in movements)
    issue_qty = sum(flt(row.issue_qty) for row in movements)
    ending_rolls = sum(flt(balances[key].rolls) for key in allowed_keys)
    ending_qty = sum(flt(balances[key].qty) for key in allowed_keys)
    return [
        {"label": _("期初匹数"), "value": opening_rolls, "datatype": "Float", "precision": 0},
        {"label": _("期初重量（Kg）"), "value": opening_qty, "datatype": "Float", "precision": 2},
        {"label": _("本期收入匹数"), "value": receipt_rolls, "datatype": "Float", "precision": 0, "indicator": "Green"},
        {"label": _("本期收入重量（Kg）"), "value": receipt_qty, "datatype": "Float", "precision": 2, "indicator": "Green"},
        {"label": _("本期发出匹数"), "value": issue_rolls, "datatype": "Float", "precision": 0, "indicator": "Orange"},
        {"label": _("本期发出重量（Kg）"), "value": issue_qty, "datatype": "Float", "precision": 2, "indicator": "Orange"},
        {"label": _("期末匹数"), "value": ending_rolls, "datatype": "Float", "precision": 0, "indicator": "Blue"},
        {"label": _("期末重量（Kg）"), "value": ending_qty, "datatype": "Float", "precision": 2, "indicator": "Blue"},
        {"label": _("流水记录数"), "value": len(movements), "datatype": "Int"},
    ]


def _key(row):
    return (row.company, row.warehouse, row.item_code, row.batch_no)


def _sort_key(row):
    return (getdate(row.posting_date), str(row.posting_time or ""), str(row.creation or ""), row.ledger_entry)


def _get_columns():
    return [
        {"label": _("过账日期"), "fieldname": "posting_date", "fieldtype": "Date", "width": 105},
        {"label": _("时间"), "fieldname": "posting_time", "fieldtype": "Time", "width": 85},
        {"label": _("流水类型"), "fieldname": "movement_type", "fieldtype": "Data", "width": 95},
        {"label": _("业务类型"), "fieldname": "business_type", "fieldtype": "Data", "width": 145},
        {"label": _("业务表单"), "fieldname": "business_doctype", "fieldtype": "Data", "width": 130},
        {"label": _("业务单号"), "fieldname": "business_document", "fieldtype": "Dynamic Link", "options": "business_doctype", "width": 155},
        {"label": _("客户"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 120},
        {"label": _("客户名称"), "fieldname": "customer_name", "fieldtype": "Data", "width": 160},
        {"label": _("匹号/批次"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 145},
        {"label": _("胚布编码"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 125},
        {"label": _("胚布名称"), "fieldname": "item_name", "fieldtype": "Data", "width": 175},
        {"label": _("颜色"), "fieldname": "color", "fieldtype": "Data", "width": 90},
        {"label": _("门幅"), "fieldname": "width", "fieldtype": "Data", "width": 80},
        {"label": _("克重"), "fieldname": "gsm", "fieldtype": "Data", "width": 80},
        {"label": _("仓库"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 165},
        {"label": _("对方仓库"), "fieldname": "counterparty_warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 165},
        {"label": _("来源仓库"), "fieldname": "s_warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
        {"label": _("目标仓库"), "fieldname": "t_warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
        {"label": _("收入匹数"), "fieldname": "receipt_roll_count", "fieldtype": "Float", "precision": 0, "width": 95},
        {"label": _("发出匹数"), "fieldname": "issue_roll_count", "fieldtype": "Float", "precision": 0, "width": 95},
        {"label": _("库存匹数"), "fieldname": "balance_roll_count", "fieldtype": "Float", "precision": 0, "width": 105},
        {"label": _("收入重量（Kg）"), "fieldname": "receipt_qty", "fieldtype": "Float", "precision": 2, "width": 120},
        {"label": _("发出重量（Kg）"), "fieldname": "issue_qty", "fieldtype": "Float", "precision": 2, "width": 120},
        {"label": _("库存重量（Kg）"), "fieldname": "balance_qty", "fieldtype": "Float", "precision": 2, "width": 135},
        {"label": _("单位"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 75},
        {"label": _("原匹号"), "fieldname": "source_batch_no", "fieldtype": "Link", "options": "Batch", "width": 130},
        {"label": _("目标匹号"), "fieldname": "target_batch_no", "fieldtype": "Link", "options": "Batch", "width": 130},
        {"label": _("生产流转卡"), "fieldname": "production_flow_card", "fieldtype": "Link", "options": "Production Flow Card", "width": 145},
        {"label": _("差异原因"), "fieldname": "difference_reason", "fieldtype": "Data", "width": 105},
        {"label": _("库存凭证类型"), "fieldname": "stock_voucher_type", "fieldtype": "Data", "width": 130},
        {"label": _("库存凭证"), "fieldname": "stock_voucher", "fieldtype": "Dynamic Link", "options": "stock_voucher_type", "width": 145},
        {"label": _("库存明细"), "fieldname": "voucher_detail_no", "fieldtype": "Data", "width": 145},
        {"label": _("经办人"), "fieldname": "created_by", "fieldtype": "Link", "options": "User", "width": 130},
        {"label": _("备注"), "fieldname": "remarks", "fieldtype": "Data", "width": 220},
        {"label": _("公司"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 130},
    ]
