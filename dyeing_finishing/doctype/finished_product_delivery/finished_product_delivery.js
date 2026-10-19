const DELIVERY_METHOD = "dyeing_finishing.dyeing_finishing.doctype.finished_product_delivery.finished_product_delivery";
function set_delivery_totals(frm) {
    const rows = frm.doc.items || [];
    frm.set_value("total_roll_count", rows.length);
    frm.set_value("total_weight", rows.reduce((sum, row) => sum + flt(row.weight), 0));
    frm.set_value("total_yard_qty", rows.reduce((sum, row) => sum + flt(row.yard_qty), 0));
}

function render_roll_selector(frm) {
    const field = frm.get_field("select_rolls_html");
    if (!field?.$wrapper) return;
    const disabled = frm.doc.docstatus !== 0 || !frm.doc.production_flow_card;
    field.$wrapper.html(`
        <button type="button" class="btn btn-sm btn-primary finished-roll-selector" ${disabled ? "disabled" : ""}>
            选择可出库成品卷
        </button>
        <span class="text-muted ml-2">可跨多张包装入库单选择，本次可全部或部分出库。</span>`);
    field.$wrapper.off("click.finishedDelivery").on("click.finishedDelivery", ".finished-roll-selector", () => select_finished_rolls(frm));
}

async function select_finished_rolls(frm) {
    const existing = new Set((frm.doc.items || []).map((row) => row.packing_receipt_item));
    const dialog = new frappe.ui.form.MultiSelectDialog({
        doctype: "Finished Product Packing Receipt Item",
        target: frm,
        setters: {},
        columns: ["匹号", "重量 (Kg)", "码数 (Y)", "当前客户", "成品卷号", "来源包装入库单"],
        add_filters_group: false,
        primary_action_label: "添加所选成品卷",
        get_query: () => ({
            query: `${DELIVERY_METHOD}.get_available_finished_rolls`,
            filters: {
                production_flow_card: frm.doc.production_flow_card,
                excluded_names: JSON.stringify([...existing]),
            },
        }),
        async action(selections) {
            const names = selections.filter((name) => !existing.has(name));
            if (!names.length) {
                dialog.dialog.hide();
                return;
            }
            const response = await frappe.call({method: `${DELIVERY_METHOD}.get_finished_roll_details`, args: {names}});
            const sources = response.message || [];
            const currentAllocation = frm.doc.items?.length
                ? `${frm.doc.customer || ""}|${frm.doc.sales_order || ""}`
                : null;
            const selectedAllocations = new Set(sources.map((row) => `${row.allocated_customer || ""}|${row.allocated_sales_order || ""}`));
            if (selectedAllocations.size > 1 || (currentAllocation && !selectedAllocations.has(currentAllocation))) {
                frappe.msgprint(__("同一张成品出库单只能选择当前客户和订单相同的成品卷。"));
                return;
            }
            sources.forEach((source) => {
                const row = frm.add_child("items");
                row.packing_receipt_item = source.name;
                ["roll_no", "source_packing_receipt", "piece_no", "finished_batch_no", "weight", "weight_uom",
                    "yard_qty", "yard_uom", "finished_grade", "quality_flag", "grey_fabric_batch", "package_no",
                    "allocated_customer", "allocated_customer_name", "allocated_sales_order", "allocated_sales_order_item",
                    "allocated_finished_item_code", "allocated_finished_product_name", "allocated_finished_specification",
                    "allocated_color_no", "allocated_color", "customer_transfer"]
                    .forEach((fieldname) => { row[fieldname] = source[fieldname]; });
            });
            const source = sources[0];
            if (source) {
                frm.set_value("customer", source.allocated_customer || "");
                frm.set_value("customer_name", source.allocated_customer_name || "");
                frm.set_value("sales_order", source.allocated_sales_order || "");
            }
            frm.refresh_field("items");
            set_delivery_totals(frm);
            dialog.dialog.hide();
        },
    });
    dialog.page_length = 1000;
    dialog.dialog.set_title("选择可出库成品卷");
    dialog.dialog.fields_dict.search_term.$wrapper.hide();
}

frappe.ui.form.on("Finished Product Delivery", {
    setup(frm) {
        frm.set_query("production_flow_card", () => ({filters: {docstatus: 1}}));
    },
    refresh(frm) {
        render_roll_selector(frm);
    },
    async production_flow_card(frm) {
        frm.clear_table("items");
        frm.refresh_field("items");
        set_delivery_totals(frm);
        if (!frm.doc.production_flow_card) {
            render_roll_selector(frm);
            return;
        }
        const response = await frappe.call({
            method: `${DELIVERY_METHOD}.get_delivery_flow_card_details`,
            args: {flow_card: frm.doc.production_flow_card},
        });
        const data = response.message || {};
        ["sales_order", "customer", "customer_name", "finished_item_code", "finished_batch_no",
            "finished_product_name", "finished_specification", "color_no", "color"]
            .forEach((fieldname) => frm.set_value(fieldname, data[fieldname] || ""));
        frm.set_value("source_warehouse", data.target_warehouse || frappe.boot.dyeing_system_settings?.finished_product_warehouse || "成品仓库 - 沅泰");
        frm.set_value("available_roll_count", data.available_roll_count || 0);
        frm.set_value("available_weight", data.available_weight || 0);
        frm.set_value("available_yard_qty", data.available_yard_qty || 0);
        render_roll_selector(frm);
    },
    items_remove(frm) {
        set_delivery_totals(frm);
    },
});
