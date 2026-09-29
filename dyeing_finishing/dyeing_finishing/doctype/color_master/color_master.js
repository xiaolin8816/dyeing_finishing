function show_color_no(frm) {
    const color_no_field = frm.fields_dict.color_no;
    if (!color_no_field) {
        return;
    }

    color_no_field.df.hidden = 0;
    if (!frm.is_new() && frm.doc.name) {
        frm.doc.color_no = frm.doc.name;
    }
    color_no_field.refresh();
    color_no_field.set_value(frm.doc.color_no || "");
}

frappe.ui.form.on("Color Master", {
    onload_post_render(frm) {
        show_color_no(frm);
    },

    refresh(frm) {
        show_color_no(frm);
    },

    after_save() {
        window.setTimeout(() => {
            frappe.set_route("List", "Color Master");
        }, 0);
    },

    customer_name(frm) {
        const customer = (frm.doc.customer_name || "").trim();
        const customer_code = customer.includes("/") ? customer.split("/", 1)[0].trim() : "";
        frm.set_value("customer_code", customer_code);
    },
});