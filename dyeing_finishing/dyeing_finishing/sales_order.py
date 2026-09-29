def make_finished_specification(item):
    width = str(item.get("custom_finished_width") or "").strip()
    gsm = str(item.get("custom_finished_gsm") or "").strip()
    gsm_uom = str(item.get("custom_finished_gsm_uom") or "").strip()

    gsm_value = f"{gsm}{gsm_uom}" if gsm else ""
    return "*".join(value for value in (width, gsm_value) if value)


def validate(doc, method=None):
    """同步页面上的客户订单号与 ERPNext 原生 po_no，并生成成品规格。"""
    if doc.custom_customer_order_no:
        doc.po_no = doc.custom_customer_order_no
    elif doc.po_no:
        doc.custom_customer_order_no = doc.po_no

    for item in doc.get("items") or []:
        item.custom_finished_specification = make_finished_specification(item)
