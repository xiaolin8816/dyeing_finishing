import frappe
from frappe import _
from frappe.utils import flt


MIN_WIDTH = 20
MAX_WIDTH = 600
REPORT_CONFIGS = {
    "Production Flow Card Progress Query": {
        "key": "production_flow_card_progress_query_report_layout",
        "user_key": "dyeing_finishing_production_flow_card_progress_query_layout",
        "fields": {
            "flow_card", "sales_order", "customer_name", "finished_product_name", "color_no", "color",
            "delivery_date", "order_qty", "production_status", "current_progress_status", "current_operation",
            "completed_operation_count", "operation_count", "grey_issue_qty", "packing_receipt_count",
            "packed_roll_count", "packed_weight", "packed_yard_qty", "packing_completion_rate",
            "delivery_count", "delivered_roll_count", "delivered_weight", "delivered_yard_qty",
            "remaining_roll_count", "remaining_weight", "remaining_yard_qty", "delivery_completion_rate",
            "last_receipt_date", "last_delivery_date", "completion_status", "is_overdue",
        },
    },
    "Finished Product Stock": {
        "key": "finished_product_stock_report_layout",
        "user_key": "dyeing_finishing_finished_product_stock_layout",
        "fields": {
            "item_code", "item_name", "color_no", "color", "specification", "customer_name",
            "warehouse", "batch_no", "production_flow_card", "sales_order", "roll_count",
            "stock_qty", "stock_uom", "yard_qty", "yard_uom", "last_receipt_date",
        },
    },
    "Finished Product Return Stock": {
        "key": "finished_product_return_stock_report_layout",
        "user_key": "dyeing_finishing_finished_product_return_stock_layout",
        "fields": {
            "production_flow_card", "customer_name", "sales_order", "finished_product_name",
            "color_no", "color", "finished_specification", "finished_batch_no", "piece_no",
            "roll_no", "return_document", "source_delivery", "return_date", "return_reason",
            "warehouse", "inspection_status", "disposal_decision", "pending_weight",
            "pending_yard_qty", "stock_days", "stock_entry",
        },
    },
    "Grey Fabric Stock": {
        "key": "grey_fabric_stock_report_column_widths",
        "user_key": "dyeing_finishing_grey_fabric_stock_layout",
        "fields": {"customer_name", "stock_source", "source_flow_card", "source_transfer", "source_batch_no", "batch_no", "item_name", "width", "gsm", "color", "stock_roll_count", "stock_qty", "receipt_roll_count", "receipt_qty", "issue_roll_count", "issue_qty", "stock_uom", "location", "warehouse", "receipt_date"},
    },
    "Production Transit Warehouse Stock": {
        "key": "production_transit_warehouse_stock_report_column_widths",
        "user_key": "dyeing_finishing_production_transit_stock_layout",
        "fields": {"customer_name", "batch_no", "item_name", "color", "stock_roll_count", "stock_qty", "stock_uom", "grey_fabric_issue", "production_flow_card", "warehouse", "transit_date"},
    },
    "Dye Material Stock": {
        "key": "dye_material_stock_report_column_widths",
        "user_key": "dyeing_finishing_dye_material_stock_layout",
        "fields": {"item_code", "item_name", "material_category", "packaging_specification", "warehouse", "actual_qty", "stock_uom", "stock_value", "last_receipt_date", "supplier_name"},
    },
    "Dye Material Return Register": {
        "key": "dye_material_return_register_report_layout",
        "user_key": "dyeing_finishing_dye_material_return_register_layout",
        "fields": {"dye_material_return", "return_date", "supplier_name", "item_code", "item_name", "return_qty_kg", "source_warehouse", "return_reason", "source_type", "stock_entry", "material_receipt_entry", "status"},
    },
}


def _get_config(report_name):
    config = REPORT_CONFIGS.get(report_name)
    if not config:
        frappe.throw(_("不支持该报表的字段布局设置"))
    return config


def _clean_layout(report_name, layout):
    config = _get_config(report_name)
    layout = frappe.parse_json(layout) or {}
    widths = layout.get("widths", layout)
    cleaned_widths = {}
    for fieldname, width in (widths or {}).items():
        width = flt(width)
        if fieldname not in config["fields"] or not width:
            continue
        if not MIN_WIDTH <= width <= MAX_WIDTH:
            frappe.throw(_("列宽应在 {0} 至 {1} 之间").format(MIN_WIDTH, MAX_WIDTH))
        cleaned_widths[fieldname] = int(width)

    def clean_field_list(values):
        result = []
        for fieldname in values or []:
            if fieldname in config["fields"] and fieldname not in result:
                result.append(fieldname)
        return result

    return {
        "widths": cleaned_widths,
        "order": clean_field_list(layout.get("order", [])),
        "hidden": clean_field_list(layout.get("hidden", [])),
        "sticky": clean_field_list(layout.get("sticky", [])),
    }


def _get_global_layout(report_name):
    config = _get_config(report_name)
    return _clean_layout(report_name, frappe.db.get_global(config["key"]) or "{}")


@frappe.whitelist()
def get_report_layout(report_name):
    config = _get_config(report_name)
    personal_layout = frappe.defaults.get_user_default(config["user_key"])
    return {
        "layout": _clean_layout(report_name, personal_layout) if personal_layout else _get_global_layout(report_name),
        "has_personal_layout": bool(personal_layout),
        "can_set_global": "System Manager" in frappe.get_roles(),
    }


@frappe.whitelist()
def set_my_report_layout(report_name, layout):
    config = _get_config(report_name)
    cleaned_layout = _clean_layout(report_name, layout)
    frappe.defaults.set_user_default(config["user_key"], frappe.as_json(cleaned_layout))
    return cleaned_layout


@frappe.whitelist()
def clear_my_report_layout(report_name):
    config = _get_config(report_name)
    frappe.defaults.clear_user_default(config["user_key"])
    return _get_global_layout(report_name)


@frappe.whitelist()
def set_global_report_layout(report_name, layout):
    frappe.only_for("System Manager")
    config = _get_config(report_name)
    cleaned_layout = _clean_layout(report_name, layout)
    frappe.db.set_global(config["key"], frappe.as_json(cleaned_layout))
    return cleaned_layout


@frappe.whitelist()
def get_stock_report_column_widths(report_name):
    return _get_global_layout(report_name)["widths"]


@frappe.whitelist()
def set_stock_report_column_widths(report_name, widths):
    frappe.only_for("System Manager")
    current_layout = _get_global_layout(report_name)
    current_layout["widths"] = widths
    return set_global_report_layout(report_name, current_layout)["widths"]
