frappe.ui.form.on("Dyeing Energy Meter", {
    setup(frm) {
        if (frm.is_new() && !frm.doc.company) {
            frm.set_value("company", frappe.defaults.get_user_default("Company") || frappe.boot.sysdefaults.company);
        }
    },
    refresh(frm) {
        ["basic_section", "scope_section", "register_section"].forEach((fieldname) => {
            frm.get_field(fieldname)?.wrapper?.addClass("dyeing-responsive-form-grid");
        });
    },
    async production_resource(frm) {
        if (!frm.doc.production_resource || frm.doc.scope_type !== "机台") return;
        const response = await frappe.db.get_value(
            "Production Resource", frm.doc.production_resource, "work_center"
        );
        await frm.set_value("work_center", response.message?.work_center || "");
    },
});
