function apply_production_actual_layout(frm) {
    ["document_section", "source_section", "source_row_2", "time_section", "quantity_section", "exception_section"]
        .forEach((fieldname) => frm.get_field(fieldname)?.wrapper?.addClass("dyeing-responsive-form-grid"));
}

frappe.ui.form.on("Dyeing Production Actual", {
    setup(frm) {
        frm.set_query("production_operation_report", () => ({
            filters: {docstatus: 1, operation_name: ["like", "%染色%"]},
        }));
    },
    refresh(frm) {
        apply_production_actual_layout(frm);
    },
    async production_operation_report(frm) {
        const name = frm.doc.production_operation_report;
        if (!name) {
            await frm.set_value("vat_no", "");
            return;
        }
        const report = await frappe.db.get_doc("Production Operation Report", name);
        if (frm.doc.production_operation_report !== name) return;
        if (report.docstatus !== 1) {
            frappe.msgprint("请选择已提交的工序报工单");
            await frm.set_value("production_operation_report", "");
            return;
        }
        const card = await frappe.db.get_doc("Production Flow Card", report.production_flow_card);
        if (frm.doc.production_operation_report !== name) return;
        const customer_name = card.customer
            ? (await frappe.db.get_value("Customer", card.customer, "customer_name")).message?.customer_name
            : "";
        await frm.set_value({
            vat_no: card.flow_card_no || card.name,
            production_flow_card: report.production_flow_card,
            customer: card.customer,
            customer_name: customer_name || card.customer,
            operation: report.operation,
            operation_name: report.operation_name,
            production_resource: report.production_resource || "",
            resource_name: report.resource_name,
            completed_qty: report.completed_qty,
            loss_qty: report.loss_qty,
            defective_qty: report.defective_qty,
            rework_qty: report.rework_qty,
            uom: report.uom,
            employee_names: (report.employees || []).map((row) => row.employee_name || row.employee).join("、"),
            company: card.company,
        });
    },
});
