const DYEING_RECEIPT_TYPE = "染料/助剂入库";
const DYEING_WAREHOUSE = "染料仓库 - 沅泰";
const dyeingReceiptMethod = "dyeing_finishing.dyeing_finishing.purchase_receipt.get_dyeing_material_items";

function isDyeingReceipt(frm) {
    return frm.doc.custom_dyeing_receipt_type === DYEING_RECEIPT_TYPE;
}

function toggleDyeingReceiptType(frm) {
    frm.toggle_display("custom_dyeing_receipt_type", isDyeingReceipt(frm));
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
        if (frm.is_new() && frappe.route_options?.custom_dyeing_receipt_type === DYEING_RECEIPT_TYPE) {
            frm.set_value("custom_dyeing_receipt_type", DYEING_RECEIPT_TYPE);
        }
        toggleDyeingReceiptType(frm);
    },
    custom_dyeing_receipt_type(frm) {
        setDyeingReceiptQuery(frm);
        toggleDyeingReceiptType(frm);
        if (!isDyeingReceipt(frm)) return;
        (frm.doc.items || []).forEach((row) => setDyeingReceiptRowDefaults(frm, row));
        frm.refresh_field("items");
    },
    items_add(frm, cdt, cdn) {
        setDyeingReceiptRowDefaults(frm, locals[cdt][cdn]);
    },
});
