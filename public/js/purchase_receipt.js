const DYEING_RECEIPT_TYPE = "染料/助剂入库";
const DYEING_WAREHOUSE = "染料仓库 - 沅泰";
const dyeingReceiptMethod = "dyeing_finishing.dyeing_finishing.purchase_receipt.get_dyeing_material_items";
const dyeingReceiptHiddenFields = [
    "section_break_42",
    "apply_discount_on",
    "base_discount_amount",
    "column_break_44",
    "additional_discount_percentage",
    "discount_amount",
    "sec_tax_breakup",
    "other_charges_calculation",
    "item_wise_tax_details",
    "pricing_rule_details",
    "pricing_rules",
    "raw_material_details",
    "get_current_stock",
    "supplied_items",
    "address_and_contact_tab",
    "section_addresses",
    "supplier_address",
    "address_display",
    "col_break_address",
    "contact_person",
    "contact_display",
    "contact_mobile",
    "contact_email",
    "section_break_98",
    "dispatch_address",
    "dispatch_address_display",
    "column_break_100",
    "shipping_address",
    "shipping_address_display",
    "billing_address_section",
    "billing_address",
    "column_break_104",
    "billing_address_display",
    "terms_tab",
    "tc_name",
    "terms",
    "more_info_tab",
    "status_section",
    "status",
    "column_break4",
    "per_billed",
    "per_returned",
    "subscription_detail",
    "auto_repeat",
    "printing_settings",
    "letter_head",
    "group_same_items",
    "column_break_97",
    "select_print_heading",
    "language",
    "transporter_info",
    "transporter_name",
    "column_break5",
    "lr_no",
    "lr_date",
    "additional_info_section",
    "instructions",
    "is_internal_supplier",
    "represents_company",
    "title",
    "inter_company_reference",
    "column_break_131",
    "remarks",
    "connections_tab",
];

function isDyeingReceipt(frm) {
    return frm.doc.custom_dyeing_receipt_type === DYEING_RECEIPT_TYPE;
}

function toggleDyeingReceiptType(frm) {
    frm.toggle_display("custom_dyeing_receipt_type", isDyeingReceipt(frm));
}

function toggleDyeingReceiptAdditionalFields(frm) {
    const showField = !isDyeingReceipt(frm);
    dyeingReceiptHiddenFields.forEach((fieldname) => frm.toggle_display(fieldname, showField));
}

function setPurchaseReceiptTitle(frm) {
    const title = isDyeingReceipt(frm)
        ? frm.is_new()
            ? __("新建染料入库")
            : __("染料入库")
        : __("采购收货单");
    frm.page.set_title(title);
    frm.page.set_title_sub(frm.is_new() ? "" : frm.doc.name);
    frappe.utils.set_title(frm.is_new() ? title : `${title} - ${frm.doc.name}`);
}

function setDyeingReceiptWarehouseDefaults(frm) {
    if (!isDyeingReceipt(frm)) return;
    if (frm.doc.docstatus) return;
    if (!frm.doc.set_warehouse) {
        frm.set_value("set_warehouse", DYEING_WAREHOUSE);
    }
    (frm.doc.items || []).forEach((row) => setDyeingReceiptRowDefaults(frm, row));
}

function setDyeingReceiptRowDefaults(frm, row) {
    if (!isDyeingReceipt(frm)) return;
    if (!row.warehouse) {
        frappe.model.set_value(row.doctype, row.name, "warehouse", DYEING_WAREHOUSE);
    }
}

function setDyeingReceiptQuery(frm) {
    frm.set_query("item_code", "items", () => {
        if (!isDyeingReceipt(frm)) return {};
        return { query: dyeingReceiptMethod };
    });
}

frappe.ui.form.on("Purchase Receipt", {
    setup(frm) {
        setDyeingReceiptQuery(frm);
    },
    refresh(frm) {
        setDyeingReceiptQuery(frm);
        toggleDyeingReceiptType(frm);
        toggleDyeingReceiptAdditionalFields(frm);
        setPurchaseReceiptTitle(frm);
        setDyeingReceiptWarehouseDefaults(frm);
    },
    custom_dyeing_receipt_type(frm) {
        setDyeingReceiptQuery(frm);
        toggleDyeingReceiptType(frm);
        toggleDyeingReceiptAdditionalFields(frm);
        setPurchaseReceiptTitle(frm);
        setDyeingReceiptWarehouseDefaults(frm);
        if (!isDyeingReceipt(frm)) return;
        frm.refresh_field("items");
    },
    items_add(frm, cdt, cdn) {
        setDyeingReceiptRowDefaults(frm, locals[cdt][cdn]);
    },
});
