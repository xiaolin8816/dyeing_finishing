import frappe
from frappe import _
from frappe.utils import flt


MIN_WIDTH = 20
MAX_WIDTH = 600
LIST_CONFIGS = {
    "Production Flow Card": {
        "key": "production_flow_card_list_layout",
        "user_key": "dyeing_finishing_production_flow_card_list_layout",
    },
    "Dye Material Other Issue": {
        "key": "dye_material_other_issue_list_layout",
        "user_key": "dyeing_finishing_dye_material_other_issue_list_layout",
    },
}


def _get_config(doctype):
    config = LIST_CONFIGS.get(doctype)
    if not config:
        frappe.throw(_("不支持该列表的字段布局设置"))
    return config


def _allowed_fields(doctype):
    fields = {field.fieldname for field in frappe.get_meta(doctype).fields if field.fieldname}
    return fields | {"name", "__status"}


def _clean_layout(doctype, layout):
    layout = frappe.parse_json(layout) or {}
    allowed = _allowed_fields(doctype)
    widths = {}
    for fieldname, width in (layout.get("widths") or {}).items():
        width = flt(width)
        if fieldname not in allowed or not width:
            continue
        if not MIN_WIDTH <= width <= MAX_WIDTH:
            frappe.throw(_("列宽应在 {0} 至 {1} 之间").format(MIN_WIDTH, MAX_WIDTH))
        widths[fieldname] = int(width)

    def clean_field_list(values):
        result = []
        for fieldname in values or []:
            if fieldname in allowed and fieldname not in result:
                result.append(fieldname)
        return result

    return {
        "widths": widths,
        "order": clean_field_list(layout.get("order")),
        "hidden": clean_field_list(layout.get("hidden")),
        "sticky": clean_field_list(layout.get("sticky")),
    }


def _get_global_layout(doctype):
    config = _get_config(doctype)
    return _clean_layout(doctype, frappe.db.get_global(config["key"]) or "{}")


@frappe.whitelist()
def get_list_layout(doctype):
    config = _get_config(doctype)
    personal_layout = frappe.defaults.get_user_default(config["user_key"])
    return {
        "layout": _clean_layout(doctype, personal_layout) if personal_layout else _get_global_layout(doctype),
        "has_personal_layout": bool(personal_layout),
        "can_set_global": "System Manager" in frappe.get_roles(),
    }


@frappe.whitelist()
def set_my_list_layout(doctype, layout):
    config = _get_config(doctype)
    cleaned_layout = _clean_layout(doctype, layout)
    frappe.defaults.set_user_default(config["user_key"], frappe.as_json(cleaned_layout))
    return cleaned_layout


@frappe.whitelist()
def clear_my_list_layout(doctype):
    config = _get_config(doctype)
    frappe.defaults.clear_user_default(config["user_key"])
    return _get_global_layout(doctype)


@frappe.whitelist()
def set_global_list_layout(doctype, layout):
    frappe.only_for("System Manager")
    config = _get_config(doctype)
    cleaned_layout = _clean_layout(doctype, layout)
    frappe.db.set_global(config["key"], frappe.as_json(cleaned_layout))
    return cleaned_layout
