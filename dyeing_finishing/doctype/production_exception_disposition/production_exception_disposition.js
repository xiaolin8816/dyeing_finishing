var exception_batches_method = "dyeing_finishing.dyeing_finishing.doctype.production_exception_disposition.production_exception_disposition.get_flow_card_batches";

function exception_batch_query(frm) {
    return { filters: { name: ["in", frm._card_batches?.length ? frm._card_batches : ["__no_matching_batch__"]] } };
}

function load_exception_batches(frm) {
    const flow_card = frm.doc.production_flow_card;
    frm._card_batches = [];
    if (!flow_card) return;
    frappe.call({
        method: exception_batches_method,
        args: { flow_card },
        callback(response) {
            if (frm.doc.production_flow_card !== flow_card) return;
            frm._card_batches = response.message || [];
            if (frm.doc.docstatus === 0 && frm._card_batches.length === 1
                && frm.doc.impact_scope !== "多个批次/匹号" && !frm.doc.batch_no) {
                frm.set_value("batch_no", frm._card_batches[0]);
            }
        },
    });
}

frappe.ui.form.on("Production Exception Disposition", {
    setup(frm) {
        frm.set_query("production_operation_report", () => ({
            filters: { docstatus: 1, ...(frm.doc.production_flow_card ? { production_flow_card: frm.doc.production_flow_card } : {}) },
        }));
        frm.set_query("dyeing_production_actual", () => ({
            filters: { docstatus: 1, production_operation_report: frm.doc.production_operation_report || "" },
        }));
        frm.set_query("material_issue", () => ({
            filters: { docstatus: 1, production_flow_card: frm.doc.production_flow_card || "" },
        }));
        frm.set_query("rework_flow_card", () => ({
            filters: { original_flow_card: frm.doc.production_flow_card || "" },
        }));
        frm.set_query("batch_no", () => exception_batch_query(frm));
        frm.set_query("batch_no", "affected_items", () => exception_batch_query(frm));
    },
    refresh(frm) {
        frm._known_card = frm.doc.production_flow_card || "";
        load_exception_batches(frm);
    },
    production_flow_card(frm) {
        const selected = frm.doc.production_flow_card || "";
        if (frm._known_card !== undefined && frm._known_card !== selected) {
            if (!frm._setting_card_from_report) frm.set_value("production_operation_report", null);
            frm.set_value("dyeing_production_actual", null);
            frm.set_value("batch_no", null);
            frm.set_value("roll_no", null);
            frm.clear_table("affected_items");
            frm.refresh_field("affected_items");
        }
        frm._known_card = selected;
        load_exception_batches(frm);
    },
    impact_scope(frm) {
        if (frm.doc.impact_scope === "多个批次/匹号") {
            frm.set_value("batch_no", null);
            frm.set_value("roll_no", null);
        } else {
            frm.clear_table("affected_items");
            frm.refresh_field("affected_items");
            if (frm.doc.impact_scope !== "指定匹号") frm.set_value("roll_no", null);
            if (frm.doc.impact_scope === "整卡/整缸" && frm._card_batches?.length !== 1) {
                frm.set_value("batch_no", null);
            } else if (frm._card_batches?.length === 1 && !frm.doc.batch_no) {
                frm.set_value("batch_no", frm._card_batches[0]);
            }
        }
    },
    batch_no(frm) {
        if (!frm.doc.batch_no && frm.doc.roll_no) frm.set_value("roll_no", null);
    },
    production_operation_report(frm) {
        if (!frm.doc.production_operation_report) return;
        const selected = frm.doc.production_operation_report;
        frappe.db.get_value("Production Operation Report", selected,
            ["production_flow_card", "loss_qty", "defective_qty", "rework_qty", "remarks"])
            .then(async ({ message }) => {
                if (!message || frm.doc.production_operation_report !== selected) return;
                frm._setting_card_from_report = true;
                try {
                    await frm.set_value("production_flow_card", message.production_flow_card);
                } finally {
                    frm._setting_card_from_report = false;
                }
                if (!frm.doc.reason && message.remarks) frm.set_value("reason", message.remarks);
                const field = { "损耗": "loss_qty", "次品": "defective_qty", "返修": "rework_qty" }[frm.doc.exception_type];
                if (field) frm.set_value("affected_qty", message[field] || 0);
            });
    },
    exception_type(frm) {
        if (frm.doc.production_operation_report) frm.trigger("production_operation_report");
    },
});
