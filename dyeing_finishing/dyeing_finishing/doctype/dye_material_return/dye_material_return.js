function set_return_item_details(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row.item_code || !frm.doc.source_warehouse) return;
    frappe.call({
        method: "dyeing_finishing.dyeing_finishing.doctype.dye_material_other_issue.dye_material_other_issue.get_dye_material_item_details",
        args: { item_code: row.item_code, warehouse: frm.doc.source_warehouse },
        callback: ({ message }) => {
            if (!message) return;
            ["item_name", "material_category", "stock_uom", "stock_qty_kg"].forEach(field => frappe.model.set_value(cdt, cdn, field, message[field]));
        }
    });
}

function set_return_totals(frm) {
    let grams = 0;
    (frm.doc.items || []).forEach(row => { grams += flt(row.return_qty_g); });
    frm.set_value("total_return_qty_g", grams);
    frm.set_value("total_return_qty_kg", flt(grams / 1000));
}

frappe.ui.form.on("Dye Material Return", {
    setup(frm) {
        frm.add_fetch("original_purchase_receipt", "supplier", "supplier");
        frm.set_query("item_code", "items", () => ({
            query: "dyeing_finishing.dyeing_finishing.doctype.dye_material_return.dye_material_return.get_dye_material_return_items"
        }));
        frm.set_query("batch_no", "items", (doc, cdt, cdn) => ({
            filters: { item: locals[cdt][cdn].item_code || "" }
        }));
    },
    source_warehouse(frm) {
        (frm.doc.items || []).forEach(row => set_return_item_details(frm, row.doctype, row.name));
    },
    refresh(frm) { set_return_totals(frm); }
});

frappe.ui.form.on("Dye Material Return Item", {
    item_code(frm, cdt, cdn) { set_return_item_details(frm, cdt, cdn); },
    return_qty_g(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, "return_qty_kg", flt(row.return_qty_g) / 1000);
        set_return_totals(frm);
    },
    items_remove(frm) { set_return_totals(frm); }
});