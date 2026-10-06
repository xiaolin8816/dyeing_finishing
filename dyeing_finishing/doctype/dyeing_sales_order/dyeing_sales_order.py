import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, nowdate


class DyeingSalesOrder(Document):
    def validate(self):
        total_qty = 0
        total_amount = 0
        for item in self.items:
            self._validate_grey_fabric_item(item)
            self._apply_color_master(item)
            item.finished_specification = self._make_finished_specification(item)
            item.amount = flt(item.qty) * flt(item.rate)
            total_qty += flt(item.qty)
            total_amount += flt(item.amount)
        self.total_qty = total_qty
        self.total_amount = total_amount
        self._set_list_summary()

    def before_update_after_submit(self):
        old_doc = self.get_doc_before_save()
        self._change_summary = self._build_change_summary(old_doc)
        if not self._change_summary:
            return
        if not (self.change_reason or "").strip():
            frappe.throw(_("修改已提交订单时必须选择修改原因"))
        current_items = {row.name for row in self.items}
        linked = frappe.get_all(
            "Production Flow Card",
            filters={"sales_order": self.name, "docstatus": ["<", 2]},
            fields=["name", "sales_order_item"],
        )
        removed_links = [row.name for row in linked if row.sales_order_item not in current_items]
        if removed_links:
            message = "订单明细已关联生产流转卡 {0}，不能删除该明细"
            frappe.throw(_(message).format("、".join(removed_links)))

    def on_update_after_submit(self):
        summary = getattr(self, "_change_summary", "")
        if not summary:
            return
        synced = self._sync_production_flow_cards()
        row = self.append(
            "change_logs",
            {
                "changed_on": now_datetime(),
                "changed_by": frappe.session.user,
                "reason": self.change_reason,
                "note": self.change_note,
                "summary": summary,
                "synced_flow_cards": "、".join(synced) if synced else "无",
            },
        )
        row.db_insert()

    def _build_change_summary(self, old_doc):
        if not old_doc:
            return ""
        changes = []
        parent_fields = {
            "customer": "客户", "customer_order_no": "客户订单号",
            "transaction_date": "订单日期", "delivery_date": "交货日期",
            "order_type": "订单类型", "order_remark": "订单备注",
        }
        for fieldname, label in parent_fields.items():
            old_value = old_doc.get(fieldname) or ""
            new_value = self.get(fieldname) or ""
            if str(old_value) != str(new_value):
                changes.append(f"{label}：{old_value or '空'} → {new_value or '空'}")

        item_fields = {
            "item_code": "物料号", "delivery_date": "出货日期", "color_no": "色号",
            "color": "颜色", "finished_product_name": "成品名称", "process_type": "加工类型",
            "finished_width": "成品门幅", "finished_gsm": "成品克重",
            "finished_gsm_uom": "克重单位", "qty": "数量", "uom": "单位",
            "rate": "单价", "order_remark": "明细备注",
        }
        old_items = {row.name: row for row in old_doc.items}
        new_items = {row.name: row for row in self.items}
        for name in sorted(set(old_items) | set(new_items)):
            old_item, new_item = old_items.get(name), new_items.get(name)
            if not old_item:
                changes.append(f"新增明细：{new_item.item_code} {new_item.item_name or ''}".strip())
                continue
            if not new_item:
                changes.append(f"删除明细：{old_item.item_code} {old_item.item_name or ''}".strip())
                continue
            prefix = new_item.item_code or old_item.item_code or name
            for fieldname, label in item_fields.items():
                old_value = old_item.get(fieldname) or ""
                new_value = new_item.get(fieldname) or ""
                if str(old_value) != str(new_value):
                    changes.append(f"{prefix} - {label}：{old_value or '空'} → {new_value or '空'}")

        for table, fieldname, label in (
            ("process_requirements", "process_requirement", "加工要求"),
            ("packaging_requirements", "packaging_requirement", "包装要求"),
        ):
            old_values = [row.get(fieldname) for row in old_doc.get(table) or []]
            new_values = [row.get(fieldname) for row in self.get(table) or []]
            if old_values != new_values:
                changes.append(f"{label}：{'、'.join(old_values) or '空'} → {'、'.join(new_values) or '空'}")
        return "\n".join(changes)

    def _sync_production_flow_cards(self):
        cards = frappe.get_all(
            "Production Flow Card",
            filters={"sales_order": self.name, "docstatus": ["<", 2]},
            pluck="name",
        )
        item_map = {row.name: row for row in self.items}
        for card_name in cards:
            card = frappe.get_doc("Production Flow Card", card_name)
            item = item_map[card.sales_order_item]
            card.update({
                "customer": self.customer,
                "customer_order_no": self.customer_order_no,
                "order_date": self.transaction_date,
                "delivery_date": self.delivery_date,
                "order_type": self.order_type,
                "process_type": item.process_type,
                "color_no": item.color_no,
                "color": item.color,
                "finished_product_name": item.finished_product_name,
                "finished_width": item.finished_width,
                "finished_gsm": item.finished_gsm,
                "finished_uom": item.uom,
                "finished_specification": item.finished_specification,
                "order_qty": item.qty,
                "production_qty": item.qty,
                "order_remarks": item.order_remark or self.order_remark,
            })
            card.set("process_requirements", [])
            for requirement in self.process_requirements:
                card.append("process_requirements", {
                    "process_requirement": requirement.process_requirement,
                    "process_requirement_name": requirement.process_requirement_name,
                })
            card.set("packaging_requirements", [])
            for requirement in self.packaging_requirements:
                card.append("packaging_requirements", {
                    "packaging_requirement": requirement.packaging_requirement,
                    "packaging_requirement_name": requirement.packaging_requirement_name,
                })
            card.flags.ignore_validate_update_after_submit = True
            card.save(ignore_permissions=True)
        return cards

    @staticmethod
    def _validate_grey_fabric_item(item):
        if not item.item_code:
            return
        item_data = frappe.db.get_value(
            "Item", item.item_code, ["item_group", "disabled"], as_dict=True
        )
        if not item_data:
            frappe.throw(f"物料 {item.item_code} 不存在")
        if item_data.disabled:
            frappe.throw(f"物料 {item.item_code} 已停用，不能用于染整销售订单")
        if item_data.item_group != "胚布":
            frappe.throw(f"物料 {item.item_code} 不属于胚布物料组，不能用于染整销售订单")

    def _set_list_summary(self):
        item = next(iter(self.items or []), None)
        self.list_finished_product_name = item.finished_product_name if item else ""
        self.list_color_no = item.color_no if item else ""
        self.list_color = item.color if item else ""

    def _apply_color_master(self, item):
        if not item.color_no:
            return
        color = frappe.db.get_value(
            "Color Master", item.color_no,
            ["color_name", "product_name", "customer_name", "status"], as_dict=True,
        )
        if not color:
            frappe.throw(f"色号 {item.color_no} 不存在")
        if color.status != "启用":
            frappe.throw(f"色号 {item.color_no} 已停用，不能用于染整销售订单")
        if color.customer_name != self.customer:
            frappe.throw(f"色号 {item.color_no} 不属于当前客户 {self.customer}")
        item.color = item.color or color.color_name
        item.finished_product_name = item.finished_product_name or color.product_name

    @staticmethod
    def _make_finished_specification(item):
        width = str(item.finished_width or "").strip()
        gsm = str(item.finished_gsm or "").strip()
        gsm_value = f"{gsm}{item.finished_gsm_uom or ''}" if gsm else ""
        return "*".join(value for value in (width, gsm_value) if value)


def _copy_requirements(source_rows, target, target_field, link_field, requirement_doctype):
    skipped = 0
    for source_row in source_rows or []:
        requirement = source_row.get(link_field)
        if not requirement or not frappe.db.exists(requirement_doctype, requirement):
            skipped += 1
            continue
        target.append(target_field, {
            link_field: requirement,
            f"{link_field}_name": source_row.get(f"{link_field}_name"),
            "description": source_row.get("description"),
        })
    return skipped


def _get_valid_color_no(source_item, customer):
    color_no = source_item.get("custom_color_no")
    if not color_no:
        return ""
    color = frappe.db.get_value(
        "Color Master", color_no, ["customer_name", "status"], as_dict=True
    )
    return color_no if color and color.status == "启用" and color.customer_name == customer else ""


@frappe.whitelist()
def migrate_erpnext_sales_orders():
    """将 ERPNext 销售订单完整复制到染整销售订单，重复执行不会重复创建。"""
    frappe.only_for("System Manager")
    result = frappe._dict(migrated=0, existing=0, skipped_empty=0, missing_color_master=0, skipped_requirements=0)
    source_names = frappe.get_all("Sales Order", pluck="name", order_by="creation asc")

    for source_name in source_names:
        if frappe.db.exists("Dyeing Sales Order", {"erpnext_sales_order": source_name}):
            result.existing += 1
            continue

        source = frappe.get_doc("Sales Order", source_name)
        if not source.items:
            result.skipped_empty += 1
            continue
        target = frappe.new_doc("Dyeing Sales Order")
        target.customer = source.customer
        target.customer_name = source.customer_name
        target.customer_order_no = source.get("custom_customer_order_no") or source.get("po_no")
        target.transaction_date = source.transaction_date or nowdate()
        target.delivery_date = source.delivery_date or source.transaction_date or nowdate()
        target.order_type = source.get("custom_dyeing_order_type") or "来料加工"
        target.company = source.company
        target.currency = source.currency
        target.order_remark = source.get("custom_production_remark")
        target.erpnext_sales_order = source.name

        for source_item in source.items:
            color_no = _get_valid_color_no(source_item, source.customer)
            if source_item.get("custom_color_no") and not color_no:
                result.missing_color_master += 1
            target.append("items", {
                "item_code": source_item.item_code,
                "item_name": source_item.item_name,
                "description": source_item.description,
                "qty": source_item.qty,
                "uom": source_item.uom or source_item.stock_uom,
                "rate": source_item.rate,
                "delivery_date": source_item.delivery_date or source.delivery_date,
                "color_no": color_no,
                "color": source_item.get("custom_color"),
                "finished_product_name": source_item.get("custom_color_product_name") or source_item.item_name,
                "process_type": source_item.get("custom_process_type") or "染色",
                "finished_width": source_item.get("custom_finished_width"),
                "finished_gsm": source_item.get("custom_finished_gsm"),
                "finished_gsm_uom": source_item.get("custom_finished_gsm_uom") or "g/㎡",
                "finished_specification": source_item.get("custom_finished_specification"),
                "order_remark": source_item.get("custom_production_remark") or source.get("custom_production_remark"),
            })

        result.skipped_requirements += _copy_requirements(
            source.get("custom_process_requirements"), target, "process_requirements", "process_requirement", "Process Requirement"
        )
        result.skipped_requirements += _copy_requirements(
            source.get("custom_packaging_requirements"), target, "packaging_requirements", "packaging_requirement", "Packaging Requirement"
        )

        target.insert(ignore_permissions=True)
        if source.docstatus == 1:
            target.submit()
        elif source.docstatus == 2:
            target.submit()
            target.cancel()
        result.migrated += 1

    frappe.db.commit()
    result.message = _("已迁移 {0} 张订单，已有 {1} 张关联订单未重复创建").format(result.migrated, result.existing)
    return result
