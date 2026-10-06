frappe.ui.form.on("Grey Fabric Master", {
    setup(frm) {
        frm.set_query("default_warehouse", () => ({
            filters: {parent_warehouse: "胚布货位 - 沅泰", is_group: 0, disabled: 0},
        }));
    },
});