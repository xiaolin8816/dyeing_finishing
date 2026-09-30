import frappe


def make_finished_specification(item):
    width = str(item.get("custom_finished_width") or "").strip()
    gsm = str(item.get("custom_finished_gsm") or "").strip()
    gsm_uom = str(item.get("custom_finished_gsm_uom") or "").strip()

    gsm_value = f"{gsm}{gsm_uom}" if gsm else ""
    return "*".join(value for value in (width, gsm_value) if value)


def apply_color_master(item, customer):
    """将已选择色号的颜色与成品名称写入销售订单明细。"""
    if not item.get("custom_color_no"):
        return

    color_master = frappe.db.get_value(
        "Color Master",
        item.custom_color_no,
        ["color_name", "product_name", "customer_name", "status"],
        as_dict=True,
    )
    if not color_master:
        frappe.throw(f"色号 {item.custom_color_no} 不存在")
    if color_master.status != "启用":
        frappe.throw(f"色号 {item.custom_color_no} 已停用，不能用于销售订单")
    if color_master.customer_name != customer:
        frappe.throw(f"色号 {item.custom_color_no} 不属于当前客户 {customer}")

    item.custom_color = color_master.color_name
    item.custom_color_product_name = color_master.product_name


def set_list_item_summary(doc):
    """将第一条物料的印染资料汇总到销售订单主表，用于主列表显示。"""
    item = next(iter(doc.get("items") or []), None)
    doc.custom_list_finished_product_name = (
        item.get("custom_color_product_name") or item.get("item_name") or ""
    ) if item else ""
    doc.custom_list_color_no = item.get("custom_color_no") or "" if item else ""
    doc.custom_list_color = item.get("custom_color") or "" if item else ""


def validate(doc, method=None):
    """同步客户订单号、色号资料与成品规格。"""
    if doc.custom_customer_order_no:
        doc.po_no = doc.custom_customer_order_no
    elif doc.po_no:
        doc.custom_customer_order_no = doc.po_no

    for item in doc.get("items") or []:
        apply_color_master(item, doc.customer)
        item.custom_finished_specification = make_finished_specification(item)

    set_list_item_summary(doc)
