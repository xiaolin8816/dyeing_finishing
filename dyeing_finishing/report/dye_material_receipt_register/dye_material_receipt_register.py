import frappe
from frappe import _


DYEING_RECEIPT_TYPE = "染料/助剂入库"


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = [
        {
            "label": _("染料入库单号"),
            "fieldname": "purchase_receipt",
            "fieldtype": "Link",
            "options": "Purchase Receipt",
            "width": 155,
        },
        {"label": _("入库日期"), "fieldname": "posting_date", "fieldtype": "Date", "width": 105},
        {"label": _("供应商"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 180},
        {"label": _("收货仓库"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 170},
        {"label": _("总数量"), "fieldname": "total_qty", "fieldtype": "Float", "precision": 2, "width": 100},
        {
            "label": _("总金额"),
            "fieldname": "grand_total",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {"label": _("状态"), "fieldname": "status", "fieldtype": "Data", "width": 100},
    ]

    receipt_filters = {"custom_dyeing_receipt_type": DYEING_RECEIPT_TYPE}
    if filters.get("from_date") and filters.get("to_date"):
        receipt_filters["posting_date"] = ["between", [filters.from_date, filters.to_date]]
    elif filters.get("from_date"):
        receipt_filters["posting_date"] = [">=", filters.from_date]
    elif filters.get("to_date"):
        receipt_filters["posting_date"] = ["<=", filters.to_date]
    if filters.get("supplier"):
        receipt_filters["supplier"] = filters.supplier

    data = frappe.get_all(
        "Purchase Receipt",
        filters=receipt_filters,
        fields=[
            "name as purchase_receipt",
            "posting_date",
            "supplier",
            "set_warehouse as warehouse",
            "total_qty",
            "grand_total",
            "currency",
            "status",
        ],
        order_by="posting_date desc, creation desc",
    )
    return columns, data
