frappe.ui.form.on("Processing Contractor", {
    setup(frm) {
        frm.set_query("supplier", () => ({ filters: { disabled: 0 } }));
        frm.set_query("service_item", () => ({ filters: { disabled: 0, is_stock_item: 0 } }));
    },
});
