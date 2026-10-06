function set_other_issue_item_details(frm, cdt, cdn) {
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

frappe.ui.form.on("Dye Material Other Issue", {
    setup(frm) {
        frm.set_query("item_code", "items", () => ({
            query: "dyeing_finishing.dyeing_finishing.doctype.dye_material_other_issue.dye_material_other_issue.get_dye_material_items"
        }));
    },
    source_warehouse(frm) {
        (frm.doc.items || []).forEach(row => set_other_issue_item_details(frm, row.doctype, row.name));
    }
});

frappe.ui.form.on("Dye Material Other Issue Item", {
    item_code(frm, cdt, cdn) { set_other_issue_item_details(frm, cdt, cdn); },
    issue_qty_g(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, "issue_qty_kg", flt(row.issue_qty_g) / 1000);
    }
});
