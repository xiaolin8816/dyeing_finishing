const CUSTOMER_TRANSFER_METHOD = "dyeing_finishing.dyeing_finishing.doctype.finished_product_customer_transfer.finished_product_customer_transfer";

function set_customer_transfer_totals(frm) {
    const rows = frm.doc.items || [];
    frm.set_value("total_roll_count", rows.length);
    frm.set_value("total_weight", rows.reduce((sum, row) => sum + flt(row.weight), 0));
    frm.set_value("total_yard_qty", rows.reduce((sum, row) => sum + flt(row.yard_qty), 0));
}

function render_stock_conversion_hint(frm) {
    const field = frm.get_field("stock_conversion_hint");
    if (!field?.$wrapper) return;
    let message = "提交后系统将根据新旧成品物料自动判断是否生成库存转换凭证。";
    let indicator = "info";
    if (frm.doc.source_finished_item_code && frm.doc.finished_item_code
        && frm.doc.source_finished_item_code === frm.doc.finished_item_code) {
        message = "新旧成品物料相同：本单只转换客户和订单归属，不生成库存转换凭证。";
        indicator = "info";
    } else if (frm.doc.stock_entry && frm.doc.docstatus === 2) {
        message = `库存转换凭证 ${frappe.utils.escape_html(frm.doc.stock_entry)} 已取消，历史关联已保留。`;
        indicator = "warning";
    } else if (frm.doc.stock_entry) {
        message = `库存转换已完成，凭证：${frappe.utils.escape_html(frm.doc.stock_entry)}。`;
        indicator = "success";
    }
    field.$wrapper.html(`<div class="alert alert-${indicator} mb-0">${message}</div>`);
}

function render_customer_transfer_selector(frm) {
    const field = frm.get_field("select_rolls_html");
    if (!field?.$wrapper) return;
    const disabled = frm.doc.docstatus !== 0 || !frm.doc.production_flow_card;
    field.$wrapper.html(`
        <button type="button" class="btn btn-sm btn-primary customer-transfer-roll-selector" ${disabled ? "disabled" : ""}>
            选择可转客户成品卷
        </button>
        <span class="text-muted ml-2">只显示尚在成品库、未出库且未在本单选中的成品卷。</span>`);
    field.$wrapper.off("click.customerTransfer").on("click.customerTransfer", ".customer-transfer-roll-selector", () => select_customer_transfer_rolls(frm));
}

async function select_customer_transfer_rolls(frm) {
    const existing = new Set((frm.doc.items || []).map((row) => row.packing_receipt_item));
    const dialog = new frappe.ui.form.MultiSelectDialog({
        doctype: "Finished Product Packing Receipt Item",
        target: frm,
        setters: {},
        columns: ["匹号", "重量(Kg)", "码数(Y)", "当前客户", "成品卷号", "来源包装入库单"],
        add_filters_group: false,
        primary_action_label: "添加所选成品卷",
        get_query: () => ({
            query: `${CUSTOMER_TRANSFER_METHOD}.get_available_customer_transfer_rolls`,
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
            const response = await frappe.call({method: `${CUSTOMER_TRANSFER_METHOD}.get_customer_transfer_roll_details`, args: {names}});
            const sources = response.message || [];
            const currentAllocation = frm.doc.items?.length ? `${frm.doc.source_customer || ""}|${frm.doc.source_sales_order || ""}|${frm.doc.source_sales_order_item || ""}` : null;
            const selectedAllocations = new Set(sources.map((row) => `${row.allocated_customer || ""}|${row.allocated_sales_order || ""}|${row.allocated_sales_order_item || ""}`));
            if (selectedAllocations.size > 1 || (currentAllocation && !selectedAllocations.has(currentAllocation))) {
                frappe.msgprint(__("同一张转客户单只能选择当前客户和订单相同的成品卷。"));
                return;
            }
            sources.forEach((source) => {
                const row = frm.add_child("items");
                row.packing_receipt_item = source.name;
                ["piece_no", "weight", "yard_qty", "finished_grade", "quality_flag", "grey_fabric_batch", "source_packing_receipt", "finished_batch_no", "roll_no"]
                    .forEach((fieldname) => { row[fieldname] = source[fieldname]; });
            });
            if (sources[0]) {
                await frm.set_value("source_customer", sources[0].allocated_customer || "");
                await frm.set_value("source_customer_name", sources[0].allocated_customer_name || "");
                await frm.set_value("source_sales_order", sources[0].allocated_sales_order || "");
                await frm.set_value("source_sales_order_item", sources[0].allocated_sales_order_item || "");
            }
            frm.refresh_field("items");
            set_customer_transfer_totals(frm);
            dialog.dialog.hide();
        },
    });
    dialog.page_length = 1000;
    dialog.dialog.set_title("选择可转客户成品卷");
    dialog.dialog.fields_dict.search_term.$wrapper.hide();
}

frappe.ui.form.on("Finished Product Customer Transfer", {
    setup(frm) {
        frm.set_query("production_flow_card", () => ({
            query: `${CUSTOMER_TRANSFER_METHOD}.get_flow_cards_with_finished_stock`,
        }));
        frm.set_query("target_sales_order", () => ({filters: {docstatus: 1}}));
        frm.set_query("target_sales_order_item", () => ({filters: {parent: frm.doc.target_sales_order || ""}}));
    },
    refresh(frm) {
        render_customer_transfer_selector(frm);
        render_stock_conversion_hint(frm);
        frm.get_field("items")?.grid?.wrapper?.find(".grid-add-row").hide();
    },
    async production_flow_card(frm) {
        frm.clear_table("items");
        frm.refresh_field("items");
        set_customer_transfer_totals(frm);
        if (!frm.doc.production_flow_card) return render_customer_transfer_selector(frm);
        const response = await frappe.call({
            method: `${CUSTOMER_TRANSFER_METHOD}.get_transfer_flow_card_details`,
            args: {flow_card: frm.doc.production_flow_card},
        });
        const data = response.message || {};
        [["source_sales_order", "sales_order"], ["source_sales_order_item", "sales_order_item"], ["source_customer", "customer"], ["source_customer_name", "customer_name"],
            ["finished_item_code", "finished_item_code"], ["finished_product_name", "finished_product_name"], ["finished_specification", "finished_specification"],
            ["color_no", "color_no"], ["color", "color"], ["finished_batch_no", "finished_batch_no"]]
            .forEach(([target, source]) => frm.set_value(target, data[source] || ""));
        const rows = data.auto_import_rolls || [];
        rows.forEach((source) => {
            const row = frm.add_child("items");
            row.packing_receipt_item = source.name;
            ["piece_no", "weight", "yard_qty", "finished_grade", "quality_flag", "grey_fabric_batch", "source_packing_receipt", "finished_batch_no", "roll_no"]
                .forEach((fieldname) => { row[fieldname] = source[fieldname]; });
        });
        if (rows[0]) {
            await frm.set_value("source_customer", rows[0].allocated_customer || "");
            await frm.set_value("source_customer_name", rows[0].allocated_customer_name || "");
            await frm.set_value("source_sales_order", rows[0].allocated_sales_order || "");
            await frm.set_value("source_sales_order_item", rows[0].allocated_sales_order_item || "");
        }
        frm.refresh_field("items");
        set_customer_transfer_totals(frm);
        if (data.skipped_roll_count) {
            frappe.show_alert({
                message: `已自动导入 ${rows.length} 卷；另外 ${data.skipped_roll_count} 卷属于其他客户、订单或成品批次，请使用选择按钮另行处理。`,
                indicator: "orange",
            }, 9);
        } else if (rows.length) {
            frappe.show_alert({message: `已自动导入 ${rows.length} 卷可转客户成品。`, indicator: "green"}, 5);
        }
        render_customer_transfer_selector(frm);
        render_stock_conversion_hint(frm);
    },
    async target_sales_order(frm) {
        await frm.set_value("target_sales_order_item", "");
        await frm.set_value("target_customer", "");
        await frm.set_value("target_customer_name", "");
        if (!frm.doc.target_sales_order) return;
        const response = await frappe.call({
            method: `${CUSTOMER_TRANSFER_METHOD}.get_target_sales_order_details`,
            args: {
                sales_order: frm.doc.target_sales_order,
                finished_product_name: frm.doc.finished_product_name || "",
                finished_specification: frm.doc.finished_specification || "",
                color_no: frm.doc.color_no || "",
                color: frm.doc.color || "",
            },
            freeze: true,
            freeze_message: "正在读取新销售订单…",
        });
        const data = response.message || {};
        await frm.set_value("target_customer", data.customer || "");
        await frm.set_value("target_customer_name", data.customer_name || "");
        const matches = data.matched_items || [];
        if (matches.length === 1) {
            await frm.set_value("target_sales_order_item", matches[0].name);
            return;
        }
        if (!matches.length) {
            frappe.msgprint(__("该销售订单没有与当前成品名称、色号、颜色和规格相符的明细。"));
            return;
        }
        frappe.show_alert({
            message: `已带出新客户名称，请从 ${matches.length} 条匹配明细中选择一条。`,
            indicator: "orange",
        }, 7);
    },
    async target_sales_order_item(frm) {
        if (!frm.doc.target_sales_order_item) return;
        const response = await frappe.call({
            method: `${CUSTOMER_TRANSFER_METHOD}.get_target_sales_order_item_details`,
            args: {sales_order_item: frm.doc.target_sales_order_item},
        });
        const row = response.message || {};
        if (row.parent && row.parent !== frm.doc.target_sales_order) {
            await frm.set_value("target_sales_order_item", "");
            frappe.msgprint(__("所选明细不属于当前新染整销售订单。"));
            return;
        }
        for (const fieldname of ["finished_product_name", "finished_specification", "color_no", "color"]) {
            await frm.set_value(fieldname, row[fieldname] || "");
        }
        render_stock_conversion_hint(frm);
    },
    items_remove(frm) {
        set_customer_transfer_totals(frm);
    },
});
