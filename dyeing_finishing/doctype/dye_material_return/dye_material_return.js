function refresh_preview_document_code(frm) {
    if (!frm.is_new() || frm.doc.document_code) return;
    frappe.call({
        method: "dyeing_finishing.dyeing_finishing.doctype.dye_material_return.dye_material_return.get_preview_document_code",
        args: { return_date: frm.doc.return_date },
        callback: ({ message }) => {
            if (message && frm.is_new() && !frm.doc.document_code) frm.set_value("document_code", message);
        }
    });
}

function set_return_totals(frm) {
    let kilograms = 0;
    (frm.doc.items || []).forEach(row => { kilograms += flt(row.return_qty_kg); });
    frm.set_value("total_return_qty_kg", flt(kilograms, 4));
}

function is_receipt_mode(frm) {
    return frm.doc.return_item_source === "原入库单带出";
}

function set_return_item_mode(frm, clear_items = false) {
    const receiptMode = is_receipt_mode(frm);
    frm.toggle_display("original_purchase_receipt", receiptMode);
    frm.set_df_property("original_purchase_receipt", "reqd", receiptMode);
    frm.set_df_property("items", "cannot_add_rows", receiptMode);
    frm.set_df_property("items", "cannot_delete_rows", 0);
    frm.set_df_property("items", "read_only", 0);
    frm.fields_dict.items.grid.update_docfield_property("item_code", "read_only", receiptMode ? 1 : 0);
    if (clear_items) {
        frm.clear_table("items");
        frm.refresh_field("items");
        set_return_totals(frm);
    }
}

function load_purchase_receipt_items(frm) {
    if (!is_receipt_mode(frm) || !frm.doc.original_purchase_receipt) {
        if (!frm.doc.original_purchase_receipt) {
            frm.clear_table("items");
            frm.refresh_field("items");
            set_return_totals(frm);
        }
        return;
    }
    frappe.call({
        method: "dyeing_finishing.dyeing_finishing.doctype.dye_material_return.dye_material_return.get_purchase_receipt_return_details",
        args: { purchase_receipt: frm.doc.original_purchase_receipt, source_warehouse: frm.doc.source_warehouse },
        freeze: true,
        freeze_message: __("正在带出原入库明细"),
        callback: ({ message }) => {
            if (!message) return;
            frm.set_value("supplier", message.supplier);
            frm.clear_table("items");
            (message.items || []).forEach(source => {
                const row = frm.add_child("items");
                Object.entries(source).forEach(([field, value]) => frappe.model.set_value(row.doctype, row.name, field, value));
            });
            frm.refresh_field("items");
            set_return_totals(frm);
            if (!(message.items || []).length) frappe.msgprint(__("该原染料入库单在退货仓库没有可退货的染料或助剂库存"));
        }
    });
}

frappe.ui.form.on("Dye Material Return", {
    setup(frm) {
        frm.set_query("item_code", "items", () => ({
            query: "dyeing_finishing.dyeing_finishing.doctype.dye_material_return.dye_material_return.get_dye_material_return_items",
            filters: { source_warehouse: frm.doc.source_warehouse }
        }));
    },
    onload(frm) {
        refresh_preview_document_code(frm);
        set_return_item_mode(frm);
    },
    return_date(frm) {
        if (frm.is_new()) frm.set_value("document_code", "").then(() => refresh_preview_document_code(frm));
    },
    return_item_source(frm) {
        frm.set_value("original_purchase_receipt", "");
        set_return_item_mode(frm, true);
    },
    original_purchase_receipt(frm) { load_purchase_receipt_items(frm); },
    source_warehouse(frm) {
        if (is_receipt_mode(frm) && frm.doc.original_purchase_receipt) load_purchase_receipt_items(frm);
        else frm.refresh_field("items");
    },
    refresh(frm) {
        set_return_item_mode(frm);
        set_return_totals(frm);
    }
});

frappe.ui.form.on("Dye Material Return Item", {
    item_code(frm, cdt, cdn) {
        if (is_receipt_mode(frm)) return;
        const row = locals[cdt][cdn];
        if (!row.item_code) return;
        frappe.call({
            method: "dyeing_finishing.dyeing_finishing.doctype.dye_material_return.dye_material_return.get_manual_return_item_details",
            args: { item_code: row.item_code, source_warehouse: frm.doc.source_warehouse },
            callback: ({ message }) => {
                if (!message) return;
                Object.entries(message).forEach(([field, value]) => frappe.model.set_value(cdt, cdn, field, value));
            }
        });
    },
    return_qty_kg(frm) { set_return_totals(frm); },
    items_remove(frm) { set_return_totals(frm); }
});
