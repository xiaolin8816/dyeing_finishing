function get_flow_card_method(method) {
    return "dyeing_finishing.dyeing_finishing.doctype.production_flow_card.production_flow_card." + method;
}

function clear_flow_card_order_data(frm) {
    ["sales_order_item", "customer", "customer_order_no", "order_date", "delivery_date", "order_type", "process_type", "color_no", "color", "finished_product_name", "finished_width", "finished_gsm", "finished_uom", "finished_specification", "order_qty", "order_remarks"].forEach((fieldname) => frm.set_value(fieldname, ""));
    frm.set_value("production_qty", 0);
    frm.clear_table("process_requirements");
    frm.clear_table("packaging_requirements");
    frm.refresh_fields();
}

function copy_requirement_rows(frm, fieldname, rows) {
    frm.clear_table(fieldname);
    (rows || []).forEach((source) => {
        const row = frm.add_child(fieldname);
        Object.assign(row, source);
    });
    frm.refresh_field(fieldname);
}

function load_sales_order_item_details(frm) {
    if (!frm.doc.sales_order || !frm.doc.sales_order_item) return;
    frappe.call({
        method: get_flow_card_method("get_sales_order_item_details"),
        args: { sales_order: frm.doc.sales_order, sales_order_item: frm.doc.sales_order_item },
        callback(response) {
            const data = response.message;
            if (!data) return;
            Object.entries(data).forEach(([fieldname, value]) => {
                if (!["process_requirements", "packaging_requirements"].includes(fieldname)) frm.set_value(fieldname, value);
            });
            copy_requirement_rows(frm, "process_requirements", data.process_requirements);
            copy_requirement_rows(frm, "packaging_requirements", data.packaging_requirements);
        },
    });
}

function keep_empty_read_only_fields_visible(frm) {
    if (!frm.is_new()) return;
    Object.values(frm.fields_dict || {}).forEach((field) => {
        if (!field || !field.df || !field.df.read_only || field.__keep_empty_read_only_visible) return;
        const original_get_status = field.get_status.bind(field);
        field.get_status = function (explain) {
            const status = original_get_status(explain);
            return frm.is_new() && this.df.read_only && !this.df.hidden && status === "None" ? "Read" : status;
        };
        field.__keep_empty_read_only_visible = true;
        field.refresh();
    });
    frm.layout.refresh_sections();
}

function select_multiple_requirements(frm, config) {
    let dialog = new frappe.ui.form.MultiSelectDialog({
        doctype: config.doctype,
        setters: {},
        add_filters_group: 0,
        primary_action_label: "添加",
        get_query: config.get_query,
        columns: config.columns,
        action(selections) {
            const existing = new Set((frm.doc[config.table] || []).map((row) => row[config.link_field]));
            selections.forEach((record_name) => {
                if (existing.has(record_name)) return;
                const row = frm.add_child(config.table);
                row[config.link_field] = record_name;
                frappe.db.get_value(config.doctype, record_name, config.source_name_field).then((response) => {
                    frappe.model.set_value(row.doctype, row.name, config.target_name_field, response.message?.[config.source_name_field] || "");
                });
            });
            frm.refresh_field(config.table);
            dialog.dialog.hide();
        },
    });
    if (config.show_all) {
        frappe.after_ajax(() => {
            if (!dialog.dialog) return;
            dialog.page_length = 1000;
            dialog.get_results();
            dialog.dialog.fields_dict.search_term?.section?.wrapper?.addClass("d-none");
        });
    }
}

function select_production_operations(frm) {
    let dialog = new frappe.ui.form.MultiSelectDialog({
        doctype: "Production Operation",
        setters: {},
        add_filters_group: 0,
        primary_action_label: "添加",
        get_query: () => ({ query: get_flow_card_method("get_production_operations_for_selection") }),
        columns: ["production_operation_code", "production_operation_name", "sequence_no"],
        action(selections) {
            const selected = new Map(dialog.get_checked_items().map((item) => [item.name, item]));
            const existing = new Set((frm.doc.operations || []).map((row) => row.operation));
            let next_sequence = (frm.doc.operations || []).length + 1;
            selections.forEach((operation_name) => {
                if (existing.has(operation_name)) return;
                const operation = selected.get(operation_name) || {};
                const row = frm.add_child("operations");
                row.operation = operation_name;
                row.operation_code = operation.production_operation_code || "";
                row.operation_name = operation.production_operation_name || "";
                row.sequence_no = operation.sequence_no || next_sequence;
                next_sequence += 1;
            });
            frm.refresh_field("operations");
            dialog.dialog.hide();
        },
    });
    frappe.after_ajax(() => {
        if (!dialog.dialog) return;
        dialog.page_length = 1000;
        dialog.get_results();
        const search_control = dialog.dialog.fields_dict.search_term;
        search_control?.section?.wrapper?.addClass("d-none");
    });
}

function setup_requirement_tabs(frm) {
    const control = frm.fields_dict.requirements_tab_controls;
    const tabs = {
        process: { label: "加工要求", section: frm.layout.sections_dict.process_requirements_section, table: "process_requirements" },
        packaging: { label: "包装要求", section: frm.layout.sections_dict.packaging_requirements_section, table: "packaging_requirements" },
        operation: { label: "生产工序", section: frm.layout.sections_dict.operations_section, table: "operations" },
    };
    if (!control || !control.$wrapper || Object.values(tabs).some((item) => !item.section)) return;

    const set_active_tab = (tab) => {
        frm.__active_requirement_tab = tab;
        Object.entries(tabs).forEach(([key, item]) => item.section.wrapper.toggleClass("d-none", key !== tab));
        const active = tabs[tab];
        const can_select_requirements = frm.is_new() || frm.doc.docstatus === 0;
        const disabled_attribute = can_select_requirements ? "" : "disabled title=\"单据已审核或已取消，不能修改明细\"";
        control.$wrapper.html(`
            <div class="d-flex align-items-center gap-2 mb-3">
                ${Object.entries(tabs).map(([key, item]) => `<button type="button" class="btn btn-sm ${key === tab ? "btn-primary" : "btn-default"}" data-requirement-tab="${key}">${item.label}</button>`).join("")}
                <button type="button" class="btn btn-sm btn-default ms-2" data-requirement-add="${tab}" ${disabled_attribute}>选择${active.label}</button>
            </div>
        `);
        control.$wrapper.find("[data-requirement-tab]").on("click", function () {
            set_active_tab($(this).data("requirement-tab"));
        });
        control.$wrapper.find("[data-requirement-add]").on("click", function () {
            if (!can_select_requirements) return;
            const table_field = tabs[$(this).data("requirement-add")].table;
            if (table_field === "operations") {
                select_production_operations(frm);
            } else if (table_field === "process_requirements") {
                select_multiple_requirements(frm, {
                    doctype: "Process Requirement",
                    table: "process_requirements",
                    link_field: "process_requirement",
                    source_name_field: "process_requirement_name",
                    target_name_field: "process_requirement_name",
                    get_query: () => ({ query: get_flow_card_method("get_process_requirements_for_selection") }),
                    columns: ["process_requirement_code", "process_requirement_name"],
                    show_all: true,
                });
            } else {
                select_multiple_requirements(frm, {
                    doctype: "Packaging Requirement",
                    table: "packaging_requirements",
                    link_field: "packaging_requirement",
                    source_name_field: "packaging_requirement_name",
                    target_name_field: "packaging_requirement_name",
                    get_query: () => ({ query: get_flow_card_method("get_packaging_requirements_for_selection") }),
                    columns: ["packaging_requirement_code", "packaging_requirement_name"],
                    show_all: true,
                });
            }
        });
    };

    set_active_tab(frm.__active_requirement_tab || "process");
}

function set_flow_card_queries(frm) {
    frm.set_query("sales_order", () => ({ filters: { docstatus: 1 } }));
    frm.set_query("sales_order_item", () => ({
        query: get_flow_card_method("get_sales_order_items"),
        filters: { sales_order: frm.doc.sales_order || "" },
    }));
    frm.set_query("batch_no", "grey_fabric_issues", () => ({
        query: get_flow_card_method("get_available_grey_fabric_batches"),
        filters: { customer: frm.doc.customer || "", order_type: frm.doc.order_type || "" },
    }));
}

function setup_production_close_actions(frm) {
    if (frm.doc.docstatus !== 1) return;
    if ((frm.doc.production_status || "进行中") === "已关闭") {
        frm.add_custom_button("重新开启生产", () => {
            frappe.confirm("重新开启后可以继续新增胚布出库和染色料单。确定继续吗？", () => {
                frappe.call({
                    method: get_flow_card_method("reopen_production_flow_card"),
                    args: { flow_card: frm.doc.name },
                    freeze: true,
                    freeze_message: "正在重新开启生产…",
                    callback() { frm.reload_doc(); },
                });
            });
        }, "生产操作");
        return;
    }
    frm.add_custom_button("关闭生产", () => {
        frappe.prompt([
            { fieldname: "closure_reason", label: "关闭原因", fieldtype: "Select", options: "客户取消\n质量异常\n胚布不足\n计划调整\n其他", reqd: 1 },
            { fieldname: "closure_remarks", label: "关闭说明", fieldtype: "Small Text" },
        ], (values) => {
            frappe.call({
                method: get_flow_card_method("close_production_flow_card"),
                args: { flow_card: frm.doc.name, closure_reason: values.closure_reason, closure_remarks: values.closure_remarks },
                freeze: true,
                freeze_message: "正在关闭生产…",
                callback() { frm.reload_doc(); },
            });
        }, "关闭生产", "确认关闭");
    }, "生产操作");
}

frappe.ui.form.on("Production Flow Card", {
    setup(frm) { set_flow_card_queries(frm); },
    refresh(frm) { set_flow_card_queries(frm); keep_empty_read_only_fields_visible(frm); setup_requirement_tabs(frm); setup_production_close_actions(frm); },
    sales_order(frm) { clear_flow_card_order_data(frm); set_flow_card_queries(frm); },
    sales_order_item(frm) { load_sales_order_item_details(frm); },
});

frappe.ui.form.on("Production Flow Card Grey Fabric Issue", {
    batch_no(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.batch_no) return;
        frappe.call({
            method: get_flow_card_method("get_batch_stock_details"),
            args: { batch_no: row.batch_no, customer: frm.doc.customer, order_type: frm.doc.order_type },
            callback(response) {
                const detail = response.message;
                if (!detail) return;
                ["grey_fabric_name", "color", "stock_roll_count", "stock_qty", "warehouse", "location"].forEach((fieldname) => frappe.model.set_value(cdt, cdn, fieldname, detail[fieldname] || ""));
            },
        });
    },
});

frappe.ui.form.on("Production Flow Card Operation", {
    operation(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.operation) return;
        frappe.db.get_value("Production Operation", row.operation, ["production_operation_code", "production_operation_name"]).then((response) => {
            const operation = response.message;
            if (!operation) return;
            frappe.model.set_value(cdt, cdn, "operation_code", operation.production_operation_code || "");
            frappe.model.set_value(cdt, cdn, "operation_name", operation.production_operation_name || "");
            if (!row.sequence_no) frappe.model.set_value(cdt, cdn, "sequence_no", (frm.doc.operations || []).length);
        });
    },
});
