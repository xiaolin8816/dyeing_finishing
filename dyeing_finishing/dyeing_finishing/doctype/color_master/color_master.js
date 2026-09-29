frappe.ui.form.on("Color Master", {
    customer_name(frm) {
        const customer = (frm.doc.customer_name || "").trim();
        const customer_code = customer.includes("/") ? customer.split("/", 1)[0].trim() : "";
        frm.set_value("customer_code", customer_code);
    },
});
