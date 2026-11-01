function apply_cost_element_layout(frm) {
    ["basic_section", "attribute_section", "usage_section", "mapping_section"].forEach((fieldname) => {
        frm.get_field(fieldname)?.wrapper?.addClass("dyeing-responsive-form-grid");
    });
}

frappe.ui.form.on("Dyeing Cost Element", {
    setup(frm) {
        if (frm.is_new() && !frm.doc.company) {
            frm.set_value("company", frappe.defaults.get_user_default("Company"));
        }
        frm.set_query("expense_account", () => ({
            filters: {
                company: frm.doc.company || "__no_company__",
                is_group: 0,
                root_type: "Expense",
            },
        }));
    },
    refresh(frm) {
        apply_cost_element_layout(frm);
    },
});
