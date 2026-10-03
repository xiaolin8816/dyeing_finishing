/* eslint-disable */
(() => {
    const GET_LAYOUT_METHOD = "dyeing_finishing.dyeing_finishing.report.stock_report_column_widths.get_report_layout";
    const SET_MY_LAYOUT_METHOD = "dyeing_finishing.dyeing_finishing.report.stock_report_column_widths.set_my_report_layout";
    const CLEAR_MY_LAYOUT_METHOD = "dyeing_finishing.dyeing_finishing.report.stock_report_column_widths.clear_my_report_layout";
    const SET_GLOBAL_LAYOUT_METHOD = "dyeing_finishing.dyeing_finishing.report.stock_report_column_widths.set_global_report_layout";
    const MIN_WIDTH = 20;
    const MAX_WIDTH = 600;

    function get_columns(report, datatable) {
        const columns = report.columns || datatable?.options?.columns || [];
        return columns.filter((column) => column.fieldname).map((column) => ({
            fieldname: column.fieldname,
            label: column.label || column.fieldname,
        }));
    }

    function ordered_columns(columns, layout) {
        const positions = new Map((layout.order || []).map((fieldname, index) => [fieldname, index]));
        return [...columns].map((column, original_index) => ({ column, original_index })).sort((left, right) => {
            const left_position = positions.has(left.column.fieldname) ? positions.get(left.column.fieldname) : 10000 + left.original_index;
            const right_position = positions.has(right.column.fieldname) ? positions.get(right.column.fieldname) : 10000 + right.original_index;
            return left_position - right_position;
        }).map((item) => item.column);
    }

    function same_column_order(current, expected) {
        return current.length === expected.length && current.every((column, index) => column.fieldname === expected[index].fieldname);
    }

    function apply_layout(report, datatable = report.datatable) {
        if (!datatable) return;
        const layout = report._dyeing_finishing_report_layout || { widths: {}, order: [] };
        const expected_columns = ordered_columns(datatable.options.columns || [], layout);
        if (!same_column_order(datatable.options.columns || [], expected_columns)) {
            datatable.refresh(datatable.options.data, expected_columns);
        }
        datatable.getColumns().forEach((column) => {
            const width = Number(layout.widths?.[column.fieldname]);
            if (Number.isFinite(width) && width >= MIN_WIDTH) {
                datatable.datamanager.updateColumn(column.colIndex, { width });
            }
        });
        datatable.style.refreshColumnWidth();
    }

    function get_position_map(columns, layout) {
        const saved_positions = new Map((layout.order || []).map((fieldname, index) => [fieldname, index + 1]));
        return Object.fromEntries(columns.map((column, index) => [column.fieldname, saved_positions.get(column.fieldname) || index + 1]));
    }

    function get_layout_from_values(columns, values) {
        const positions = [];
        const widths = {};
        const used_positions = new Set();
        for (const column of columns) {
            const position = Number(values[`position_${column.fieldname}`]);
            const width = Number(values[`width_${column.fieldname}`]);
            if (!Number.isInteger(position) || position < 1 || position > columns.length || used_positions.has(position)) {
                frappe.throw("每个字段的显示顺序必须是 1 至 " + columns.length + " 之间且不可重复的整数。");
            }
            if (width && (width < MIN_WIDTH || width > MAX_WIDTH)) {
                frappe.throw("列宽应在 " + MIN_WIDTH + " 至 " + MAX_WIDTH + " 之间。");
            }
            used_positions.add(position);
            positions.push({ fieldname: column.fieldname, position });
            if (width) widths[column.fieldname] = width;
        }
        return { widths, order: positions.sort((left, right) => left.position - right.position).map((item) => item.fieldname) };
    }

    function show_layout_dialog(report, report_name, can_set_global) {
        const columns = get_columns(report);
        if (!columns.length) {
            frappe.msgprint("请先等待报表数据加载完成，再调整字段布局。");
            return;
        }
        const layout = report._dyeing_finishing_report_layout || { widths: {}, order: [] };
        const positions = get_position_map(columns, layout);
        const fields = [];
        columns.forEach((column) => {
            fields.push({ fieldtype: "Section Break", label: column.label });
            fields.push({ label: "显示顺序", fieldname: `position_${column.fieldname}`, fieldtype: "Int", default: positions[column.fieldname], reqd: 1 });
            fields.push({ label: "宽度", fieldname: `width_${column.fieldname}`, fieldtype: "Int", default: layout.widths?.[column.fieldname] || "", description: `可填写 ${MIN_WIDTH} 至 ${MAX_WIDTH}` });
        });
        if (can_set_global) {
            fields.push({ fieldtype: "Section Break", label: "管理员设置" });
            fields.push({ label: "设为全员默认布局", fieldname: "apply_to_all", fieldtype: "Check", description: "勾选后，未设置个人布局的用户将使用此布局。" });
        }
        const dialog = new frappe.ui.Dialog({
            title: "调整字段布局",
            fields,
            primary_action_label: "保存布局",
            primary_action(values) {
                const next_layout = get_layout_from_values(columns, values);
                const method = values.apply_to_all ? SET_GLOBAL_LAYOUT_METHOD : SET_MY_LAYOUT_METHOD;
                frappe.call({ method, args: { report_name: report_name, layout: next_layout } }).then((response) => {
                    report._dyeing_finishing_report_layout = response.message || next_layout;
                    dialog.hide();
                    report.refresh();
                    frappe.show_alert({ message: values.apply_to_all ? "已设为全员默认布局" : "我的字段布局已保存", indicator: "green" });
                });
            },
        });
        dialog.set_secondary_action_label("恢复我的默认布局");
        dialog.set_secondary_action(() => {
            frappe.call({ method: CLEAR_MY_LAYOUT_METHOD, args: { report_name: report_name } }).then((response) => {
                report._dyeing_finishing_report_layout = response.message || { widths: {}, order: [] };
                dialog.hide();
                report.refresh();
                frappe.show_alert({ message: "已恢复默认布局", indicator: "green" });
            });
        });
        dialog.show();
    }

    window.dyeing_finishing_report_layout = {
        register({ report_name, filters = [], onload }) {
            let current_report;
            frappe.query_reports[report_name] = {
                filters,
                onload(report) {
                    current_report = report;
                    if (onload) onload(report);
                    frappe.call({ method: GET_LAYOUT_METHOD, args: { report_name } }).then((response) => {
                        const result = response.message || {};
                        report._dyeing_finishing_report_layout = result.layout || { widths: {}, order: [] };
                        report._dyeing_finishing_can_set_global_layout = result.can_set_global;
                        report.refresh();
                    });
                    report.page.add_menu_item("调整字段布局", () => {
                        show_layout_dialog(report, report_name, report._dyeing_finishing_can_set_global_layout);
                    });
                },
                get_datatable_options(options) {
                    const layout = current_report?._dyeing_finishing_report_layout;
                    if (layout) options.columns = ordered_columns(options.columns || [], layout);
                    return options;
                },
                after_datatable_render(datatable) {
                    if (current_report) apply_layout(current_report, datatable);
                },
            };
        },
    };
})();