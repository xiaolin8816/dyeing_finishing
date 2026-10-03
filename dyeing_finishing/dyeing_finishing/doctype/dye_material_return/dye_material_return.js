function refresh_preview_document_code(frm) {
    if (!frm.is_new() || frm.doc.document_code) return;
    frappe.call({
        method: "dyeing_finishing.dyeing_finishing.doctype.dye_material_return.dye_material_return.get_preview_document_code",
        args: { return_date: frm.doc.return_date },
        callback: ({ message }) => {
            if (message && frm.is_new() && !frm.doc.document_code) frm.set_value("document_code", message);
        }
    });
}

function set_return_totals(frm) {
    let grams = 0;
    (frm.doc.items || []).forEach(row => { grams += flt(row.return_qty_g); });
    frm.set_value("total_return_qty_g", grams);
    frm.set_value("total_return_qty_kg", flt(grams / 1000));
}

function load_purchase_receipt_items(frm) {
    if (!frm.doc.original_purchase_receipt) {
        frm.clear_table("items");
        frm.refresh_field("items");
        set_return_totals(frm);
        return;
    }
    frappe.call({
        method: "dyeing_finishing.dyeing_finishing.doctype.dye_material_return.dye_material_return.get_purchase_receipt_return_details",
        args: { purchase_receipt: frm.doc.original_purchase_receipt },
        freeze: true,
        freeze_message: __("正在带出原入库明细"),
        callback: ({ message }) => {
            if (!message) return;
            frm.set_value("supplier", message.supplier);
            frm.clear_table("items");
            (message.items || []).forEach(source => {
                const row = frm.add_child("items");
                Object.entries(source).forEach(([field, value]) => frappe.model.set_value(row.doctype, row.name, field, value));
            });
            frm.refresh_field("items");
            set_return_totals(frm);
            if (!(message.items || []).length) frappe.msgprint(__("该原染料入库单没有可退货的染料或助剂明细"));
        }
    });
}

frappe.ui.form.on("Dye Material Return", {
    setup(frm) {
        frm.set_df_property("items", "cannot_add_rows", 1);
        frm.set_df_property("items", "cannot_delete_rows", 1);
    },
    onload(frm) { refresh_preview_document_code(frm); },
    return_date(frm) {
        if (frm.is_new()) frm.set_value("document_code", "").then(() => refresh_preview_document_code(frm));
    },
    original_purchase_receipt(frm) { load_purchase_receipt_items(frm); },
    refresh(frm) { set_return_totals(frm); }
});

frappe.ui.form.on("Dye Material Return Item", {
    return_qty_g(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, "return_qty_kg", flt(row.return_qty_g) / 1000);
        set_return_totals(frm);
    },
    items_remove(frm) { set_return_totals(frm); }
});