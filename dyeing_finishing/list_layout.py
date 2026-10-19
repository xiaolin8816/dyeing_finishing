import frappe
from frappe import _
from frappe.utils import flt


MIN_WIDTH = 20
MAX_WIDTH = 600
LIST_CONFIGS = {
    "Process Requirement": {"doctype": "Process Requirement", "key": "process_requirement_list_layout", "user_key": "dyeing_finishing_process_requirement_list_layout"},
    "Packaging Requirement": {"doctype": "Packaging Requirement", "key": "packaging_requirement_list_layout", "user_key": "dyeing_finishing_packaging_requirement_list_layout"},
    "Production Operation": {"doctype": "Production Operation", "key": "production_operation_list_layout", "user_key": "dyeing_finishing_production_operation_list_layout"},
    "Process Parameter Template": {"doctype": "Process Parameter Template", "key": "process_parameter_template_list_layout", "user_key": "dyeing_finishing_process_parameter_template_list_layout"},
    "Production Work Center": {"doctype": "Production Work Center", "key": "production_work_center_list_layout", "user_key": "dyeing_finishing_production_work_center_list_layout"},
    "Production Resource": {"doctype": "Production Resource", "key": "production_resource_list_layout", "user_key": "dyeing_finishing_production_resource_list_layout"},
    "Grey Fabric Master": {"doctype": "Grey Fabric Master", "key": "grey_fabric_master_list_layout", "user_key": "dyeing_finishing_grey_fabric_master_list_layout"},
    "Dyeing Item Group": {"doctype": "Item Group", "key": "dyeing_item_group_list_layout", "user_key": "dyeing_finishing_item_group_list_layout"},
    "Dyeing Company": {"doctype": "Company", "key": "dyeing_company_list_layout", "user_key": "dyeing_finishing_company_list_layout"},
    "Dyeing Customer": {"doctype": "Customer", "key": "dyeing_customer_list_layout", "user_key": "dyeing_finishing_customer_list_layout"},
    "Dyeing Supplier": {"doctype": "Supplier", "key": "dyeing_supplier_list_layout", "user_key": "dyeing_finishing_supplier_list_layout"},
    "Dyeing Employee": {"doctype": "Employee", "key": "dyeing_employee_list_layout", "user_key": "dyeing_finishing_employee_list_layout"},
    "Dyeing UOM": {"doctype": "UOM", "key": "dyeing_uom_list_layout", "user_key": "dyeing_finishing_uom_list_layout"},
    "Dyeing Purchase Receipt": {"doctype": "Purchase Receipt", "key": "dyeing_purchase_receipt_list_layout", "user_key": "dyeing_finishing_purchase_receipt_list_layout"},
    "Color Master": {"doctype": "Color Master", "key": "color_master_list_layout", "user_key": "dyeing_finishing_color_master_list_layout"},
    "Laboratory Recipe": {"doctype": "Laboratory Recipe", "key": "laboratory_recipe_list_layout", "user_key": "dyeing_finishing_laboratory_recipe_list_layout"},
    "Customer Grey Fabric Receipt": {"doctype": "Customer Grey Fabric Receipt", "key": "customer_grey_fabric_receipt_list_layout", "user_key": "dyeing_finishing_customer_grey_fabric_receipt_list_layout"},
    "Grey Fabric Issue": {"doctype": "Grey Fabric Issue", "key": "grey_fabric_issue_list_layout", "user_key": "dyeing_finishing_grey_fabric_issue_list_layout"},
    "Grey Fabric Customer Transfer": {"doctype": "Grey Fabric Customer Transfer", "key": "grey_fabric_customer_transfer_list_layout", "user_key": "dyeing_finishing_grey_fabric_customer_transfer_list_layout"},
    "Production Shift": {"doctype": "Production Shift", "key": "production_shift_list_layout", "user_key": "dyeing_finishing_production_shift_list_layout"},
    "Machine Production Calendar": {"doctype": "Machine Production Calendar", "key": "machine_production_calendar_list_layout", "user_key": "dyeing_finishing_machine_production_calendar_list_layout"},
    "Dyeing Production Schedule": {"doctype": "Dyeing Production Schedule", "key": "dyeing_production_schedule_list_layout", "user_key": "dyeing_finishing_production_schedule_list_layout"},
    "Customer Grey Fabric Return": {"doctype": "Customer Grey Fabric Return", "key": "customer_grey_fabric_return_list_layout", "user_key": "dyeing_finishing_customer_grey_fabric_return_list_layout"},
    "Dyeing Sales Order": {"doctype": "Dyeing Sales Order", "key": "dyeing_sales_order_list_layout", "user_key": "dyeing_finishing_dyeing_sales_order_list_layout"},
    "Site Dyeing Material Sheet": {"doctype": "Site Dyeing Material Sheet", "key": "site_dyeing_material_sheet_list_layout", "user_key": "dyeing_finishing_site_dyeing_material_sheet_list_layout"},
    "Site Dyeing Material Issue": {"doctype": "Site Dyeing Material Issue", "key": "site_dyeing_material_issue_list_layout", "user_key": "dyeing_finishing_site_dyeing_material_issue_list_layout"},
    "Dye Material Return": {"doctype": "Dye Material Return", "key": "dye_material_return_list_layout", "user_key": "dyeing_finishing_dye_material_return_list_layout"},
    "Finished Product Packing Receipt": {"doctype": "Finished Product Packing Receipt", "key": "finished_product_packing_receipt_list_layout", "user_key": "dyeing_finishing_finished_product_packing_receipt_list_layout"},
    "Finished Product Delivery": {"doctype": "Finished Product Delivery", "key": "finished_product_delivery_list_layout", "user_key": "dyeing_finishing_finished_product_delivery_list_layout"},
    "Finished Product Customer Transfer": {"doctype": "Finished Product Customer Transfer", "key": "finished_product_customer_transfer_list_layout", "user_key": "dyeing_finishing_finished_product_customer_transfer_list_layout"},
    "Finished Product Return": {"doctype": "Finished Product Return", "key": "finished_product_return_list_layout", "user_key": "dyeing_finishing_finished_product_return_list_layout"},
    "Finished Product Return to Grey Fabric": {"doctype": "Finished Product Return to Grey Fabric", "key": "finished_product_return_to_grey_fabric_list_layout", "user_key": "dyeing_finishing_finished_product_return_to_grey_fabric_list_layout"},
    "Finished Product to Grey Fabric": {"doctype": "Finished Product to Grey Fabric", "key": "finished_product_to_grey_fabric_list_layout", "user_key": "dyeing_finishing_finished_product_to_grey_fabric_list_layout"},
    "Finished Product Blank Label": {"doctype": "Finished Product Blank Label", "key": "finished_product_blank_label_list_layout", "user_key": "dyeing_finishing_finished_product_blank_label_list_layout"},
    "Production Flow Card": {
        "doctype": "Production Flow Card",
        "key": "production_flow_card_list_layout",
        "user_key": "dyeing_finishing_production_flow_card_list_layout",
    },
    "Production Operation Report": {
        "doctype": "Production Operation Report",
        "key": "production_operation_report_list_layout",
        "user_key": "dyeing_finishing_production_operation_report_list_layout",
    },
    "Employee Operation Permission": {
        "doctype": "Employee Operation Permission",
        "key": "employee_operation_permission_list_layout",
        "user_key": "dyeing_finishing_employee_operation_permission_list_layout",
    },
    "Dye Material Other Issue": {
        "doctype": "Dye Material Other Issue",
        "key": "dye_material_other_issue_list_layout",
        "user_key": "dyeing_finishing_dye_material_other_issue_list_layout",
    },
    "Dyeing Material Item": {
        "doctype": "Item",
        "key": "dyeing_material_item_list_layout",
        "user_key": "dyeing_finishing_dyeing_material_item_list_layout",
    },
    "Finished Product Item": {
        "doctype": "Item",
        "key": "finished_product_item_list_layout",
        "user_key": "dyeing_finishing_finished_product_item_list_layout",
    },
}


def _get_config(doctype):
    config = LIST_CONFIGS.get(doctype)
    if not config:
        frappe.throw(_("不支持该列表的字段布局设置"))
    return config


def _allowed_fields(layout_name):
    config = _get_config(layout_name)
    fields = {field.fieldname for field in frappe.get_meta(config["doctype"]).fields if field.fieldname}
    fields.discard("custom_is_dyeing_material")
    fields.discard("custom_is_finished_product")
    fields.discard("custom_finished_identity_key")
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
