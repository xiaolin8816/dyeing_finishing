// Copyright (c) 2026, Xiaolin Hang and contributors
// For license information, please see license.txt

frappe.ui.form.on("Production Operation", {
    setup(frm) {
        frm.set_query("parent_production_operation", () => ({
            filters: {
                parent_production_operation: ["is", "not set"],
                production_operation_code: ["like", "___"],
            },
        }));
    },

    refresh(frm) {
        frm.trigger("set_code_editability");
        if (frm.is_new()) {
            frm.trigger("set_operation_code");
        }
    },

    parent_production_operation(frm) {
        frm.trigger("set_code_editability");
        if (frm.is_new()) {
            frm.trigger("set_operation_code");
        }
    },

    set_operation_code(frm) {
        const method = frm.doc.parent_production_operation
            ? "dyeing_finishing.dyeing_finishing.doctype.production_operation.production_operation.get_next_child_operation_code"
            : "dyeing_finishing.dyeing_finishing.doctype.production_operation.production_operation.get_next_main_operation_code";
        const args = frm.doc.parent_production_operation
            ? { parent_operation: frm.doc.parent_production_operation }
            : {};

        frappe.call({
            method,
            args,
            callback(response) {
                if (response.message && frm.is_new()) {
                    frm.set_value("production_operation_code", response.message);
                }
            },
        });
    },

    set_code_editability(frm) {
        frm.set_df_property("production_operation_code", "read_only", frm.is_new());
    },
});
