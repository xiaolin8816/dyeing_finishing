frappe.ui.form.on("Dyeing Flow Card Cost Settlement", {
    setup(frm) {
        frm.set_query("production_flow_card", () => ({
            query: "dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement.available_flow_cards",
        }));
    },
    refresh(frm) {
        if (frm.doc.docstatus !== 0 || frm.is_new()) return;
        frm.add_custom_button("刷新成本来源", () => {
            frm.save().then(() => frm.reload_doc());
        });
        const pending = (frm.doc.items || []).filter(row => row.source_doctype === "Dyeing Energy Allocation" && ["待计价", "人工补录"].includes(row.pricing_status));
        if (!pending.length) return;
        frm.add_custom_button("补录能源单价", () => {
            const options = pending.map(row => ({ label: `${row.description} (${row.quantity} ${row.uom})`, value: row.source_detail }));
            const dialog = new frappe.ui.Dialog({
                title: "补录能源单价",
                fields: [
                    { fieldname: "source_detail", label: "能源分摊明细", fieldtype: "Select", options, reqd: 1 },
                    { fieldname: "rate", label: "单价", fieldtype: "Currency", reqd: 1 },
                    { fieldname: "basis", label: "补录依据", fieldtype: "Small Text", reqd: 1 },
                ],
                primary_action_label: "保存",
                primary_action(values) {
                    frappe.call({
                        method: "dyeing_finishing.dyeing_finishing.doctype.dyeing_flow_card_cost_settlement.dyeing_flow_card_cost_settlement.set_energy_price",
                        args: { settlement: frm.doc.name, ...values },
                        freeze: true,
                        callback(response) {
                            if (response.message) {
                                dialog.hide();
                                frm.reload_doc();
                            }
                        },
                    });
                },
            });
            dialog.show();
        });
    },
});
