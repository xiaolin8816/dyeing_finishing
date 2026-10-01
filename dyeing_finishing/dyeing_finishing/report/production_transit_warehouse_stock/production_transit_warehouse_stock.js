/* eslint-disable */
(() => {
    const REPORT_NAME = "Production Transit Warehouse Stock";
    const GET_WIDTHS_METHOD = "dyeing_finishing.dyeing_finishing.report.stock_report_column_widths.get_stock_report_column_widths";
    const SET_WIDTHS_METHOD = "dyeing_finishing.dyeing_finishing.report.stock_report_column_widths.set_stock_report_column_widths";
    const MIN_WIDTH = 20;
    const MAX_WIDTH = 600;
    let current_report;

    function get_columns(report) {
        return (report.columns || []).filter((column) => column.fieldname).map((column) => ({
            fieldname: column.fieldname,
            label: column.label || column.fieldname,
        }));
    }

    function apply_widths(report, datatable = report.datatable) {
        if (!datatable) return;
        const widths = report._stock_report_column_widths || {};
        datatable.getColumns().forEach((column) => {
            const width = Number(widths[column.fieldname]);
            if (!Number.isFinite(width) || width < MIN_WIDTH) return;
            datatable.datamanager.updateColumn(column.colIndex, { width });
        });
        // DataTable 会同时更新表头和内容列，避免出现错位。
        datatable.style.refreshColumnWidth();
    }

    function load_widths(report) {
        return frappe.call({
            method: GET_WIDTHS_METHOD,
            args: { report_name: REPORT_NAME },
        }).then((response) => {
            report._stock_report_column_widths = response.message || {};
            apply_widths(report);
        });
    }

    function show_width_dialog(report) {
        const columns = get_columns(report);
        if (!columns.length) {
            frappe.msgprint("请先等待报表数据加载完成，再调整列宽。");
            return;
        }
        const widths = report._stock_report_column_widths || {};
        const dialog = new frappe.ui.Dialog({
            title: "调整列表列宽",
            fields: columns.map((column) => ({
                label: `${column.label}宽度`,
                fieldname: `width_${column.fieldname}`,
                fieldtype: "Int",
                default: widths[column.fieldname] || "",
                description: `可填写 ${MIN_WIDTH} 至 ${MAX_WIDTH}`,
            })),
            primary_action_label: "保存并应用给所有用户",
            primary_action(values) {
                const next_widths = {};
                let has_invalid_width = false;
                columns.forEach((column) => {
                    const width = Number(values[`width_${column.fieldname}`]);
                    if (!width) return;
                    if (width < MIN_WIDTH || width > MAX_WIDTH) {
                        has_invalid_width = true;
                        return;
                    }
                    next_widths[column.fieldname] = width;
                });
                if (has_invalid_width) {
                    frappe.msgprint(`列宽应在 ${MIN_WIDTH} 至 ${MAX_WIDTH} 之间。`);
                    return;
                }
                frappe.call({
                    method: SET_WIDTHS_METHOD,
                    args: { report_name: REPORT_NAME, widths: next_widths },
                }).then((response) => {
                    report._stock_report_column_widths = response.message || {};
                    apply_widths(report);
                    dialog.hide();
                    frappe.show_alert({ message: "列表列宽已应用给所有用户", indicator: "green" });
                });
            },
        });
        dialog.set_secondary_action_label("恢复所有用户默认宽度");
        dialog.set_secondary_action(() => {
            frappe.call({
                method: SET_WIDTHS_METHOD,
                args: { report_name: REPORT_NAME, widths: {} },
            }).then(() => {
                report._stock_report_column_widths = {};
                dialog.hide();
                report.refresh();
            });
        });
        dialog.show();
    }

    frappe.query_reports[REPORT_NAME] = {
        filters: [],
        onload(report) {
            current_report = report;
            load_widths(report);
            if (frappe.user.has_role("System Manager")) {
                report.page.add_menu_item("调整列表列宽", () => show_width_dialog(report));
            }
        },
        after_datatable_render(datatable) {
            if (current_report) apply_widths(current_report, datatable);
        },
    };
})();
