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
        const hidden = new Set(layout.hidden || []);
        return [...columns].filter((column) => !hidden.has(column.fieldname)).map((column, original_index) => ({ column, original_index })).sort((left, right) => {
            const left_position = positions.has(left.column.fieldname) ? positions.get(left.column.fieldname) : 10000 + left.original_index;
            const right_position = positions.has(right.column.fieldname) ? positions.get(right.column.fieldname) : 10000 + right.original_index;
            return left_position - right_position;
        }).map((item) => item.column);
    }

    function configured_columns(columns, layout) {
        const ordered = ordered_columns(columns, layout);
        const visible = ordered.map((column) => column.fieldname).filter(Boolean);
        const sticky = new Set(get_sticky_fields(visible, get_sticky_end(visible, layout.sticky || [])));
        return ordered.map((column) => {
            const width = Number(layout.widths?.[column.fieldname]);
            return {
                ...column,
                sticky: sticky.has(column.fieldname),
                ...(Number.isFinite(width) && width >= MIN_WIDTH ? { width } : {}),
            };
        });
    }

    function same_column_order(current, expected) {
        return current.length === expected.length && current.every((column, index) => column.fieldname === expected[index].fieldname);
    }

    function get_sticky_end(visible, sticky) {
        const sticky_fields = new Set(sticky || []);
        let sticky_end = "";
        visible.forEach((fieldname) => {
            if (sticky_fields.has(fieldname)) sticky_end = fieldname;
        });
        return sticky_end;
    }

    function get_sticky_fields(visible, sticky_end) {
        const sticky_index = visible.indexOf(sticky_end);
        return sticky_index >= 0 ? visible.slice(0, sticky_index + 1) : [];
    }

    function apply_layout(report, datatable = report.datatable) {
        if (!datatable) return;
        const layout = report._dyeing_finishing_report_layout || { widths: {}, order: [], hidden: [], sticky: [] };
        const expected_columns = ordered_columns(datatable.options.columns || [], layout);
        if (!same_column_order(datatable.options.columns || [], expected_columns)) {
            datatable.refresh(datatable.options.data, expected_columns);
        }
        const visible = expected_columns.map((column) => column.fieldname).filter(Boolean);
        const sticky = new Set(get_sticky_fields(visible, get_sticky_end(visible, layout.sticky || [])));
        datatable.getColumns().forEach((column) => {
            const width = Number(layout.widths?.[column.fieldname]);
            const updates = {};
            if (Number.isFinite(width) && width >= MIN_WIDTH) updates.width = width;
            datatable.datamanager.updateColumn(column.colIndex, updates);
            datatable.setColumnSticky(column.colIndex, sticky.has(column.fieldname));
        });
        datatable.style.refreshColumnWidth();
    }

    function escape_html(value) {
        return frappe.utils.escape_html ? frappe.utils.escape_html(value) : String(value).replace(/[&<>"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[character]);
    }

    function render_rows(dialog, columns, state) {
        const visible = state.visible.filter((fieldname) => columns.some((column) => column.fieldname === fieldname));
        state.visible = visible;
        const by_name = Object.fromEntries(columns.map((column) => [column.fieldname, column]));
        const rows = visible.map((fieldname) => {
            const column = by_name[fieldname];
            return `<div class="sortable report-layout-row border rounded mb-2 px-2 py-1" data-fieldname="${fieldname}">
                <div class="row align-items-center">
                    <div class="col-1 d-flex justify-content-center sortable-handle" style="cursor: grab;">${frappe.utils.icon("drag", "xs")}</div>
                    <div class="col-4">${escape_html(column.label)}</div>
                    <div class="col-2"><input class="form-control form-control-sm report-layout-width" type="number" min="${MIN_WIDTH}" max="${MAX_WIDTH}" value="${state.widths[fieldname] || ""}" data-fieldname="${fieldname}"></div>
                    <div class="col-3 text-center"><input class="report-layout-sticky-end" type="radio" name="report-layout-sticky-end" value="${fieldname}" aria-label="固定至${escape_html(column.label)}" title="从左侧第一列固定至${escape_html(column.label)}" ${state.sticky_end === fieldname ? "checked" : ""}></div>
                    <div class="col-2 text-center"><a class="text-muted report-layout-remove" data-fieldname="${fieldname}" title="隐藏字段">${frappe.utils.icon("trash", "xs")}</a></div>
                </div>
            </div>`;
        }).join("");
        const wrapper = dialog.get_field("columns_html").$wrapper;
        wrapper.html(`<div class="row text-muted mb-2"><div class="col-1"></div><div class="col-4">字段名</div><div class="col-2">宽度</div><div class="col-3 text-center">固定至</div><div class="col-2"></div></div><div class="row mb-2"><div class="col-7"></div><div class="col-3 text-center"><label class="mb-0"><input class="report-layout-sticky-end" type="radio" name="report-layout-sticky-end" value="" ${state.sticky_end ? "" : "checked"}> 不固定任何列</label></div></div><div class="report-layout-rows">${rows}</div><div class="small text-muted mb-2">从左侧第一列起，连续固定至所选列。</div><a class="text-muted report-layout-select-fields">+ 添加/移除列</a>`);
        new Sortable(wrapper.find(".report-layout-rows")[0], { handle: ".sortable-handle", draggable: ".sortable", animation: 150, onUpdate: () => {
            state.visible = wrapper.find(".report-layout-row").map((_, row) => row.dataset.fieldname).get();
        }});
        wrapper.find(".report-layout-width").on("change", (event) => { state.widths[event.target.dataset.fieldname] = Number(event.target.value) || ""; });
        wrapper.find(".report-layout-sticky-end").on("change", (event) => { if (event.target.checked) state.sticky_end = event.target.value; });
        wrapper.find(".report-layout-remove").on("click", (event) => { const fieldname = event.currentTarget.dataset.fieldname; state.visible = state.visible.filter((item) => item !== fieldname); if (state.sticky_end === fieldname) state.sticky_end = ""; render_rows(dialog, columns, state); });
        wrapper.find(".report-layout-select-fields").on("click", () => show_column_selector(dialog, columns, state));
    }

    function show_column_selector(parent_dialog, columns, state) {
        const selected = new Set(state.visible);
        const selector = new frappe.ui.Dialog({
            title: "添加/移除列",
            fields: columns.map((column) => ({ label: column.label, fieldname: `show_${column.fieldname}`, fieldtype: "Check", default: selected.has(column.fieldname) ? 1 : 0 })),
            primary_action_label: "确定",
            primary_action(values) {
                const next_visible = columns.filter((column) => values[`show_${column.fieldname}`]).map((column) => column.fieldname);
                if (!next_visible.length) { frappe.msgprint("请至少保留一个字段。"); return; }
                state.visible = state.visible.filter((fieldname) => next_visible.includes(fieldname));
                next_visible.forEach((fieldname) => { if (!state.visible.includes(fieldname)) state.visible.push(fieldname); });
                if (!state.visible.includes(state.sticky_end)) state.sticky_end = "";
                selector.hide();
                render_rows(parent_dialog, columns, state);
            },
        });
        selector.show();
    }

    function show_layout_dialog(report, report_name, can_set_global) {
        const columns = get_columns(report);
        if (!columns.length) { frappe.msgprint("请先等待报表数据加载完成，再调整列设置。"); return; }
        const layout = report._dyeing_finishing_report_layout || { widths: {}, order: [], hidden: [], sticky: [] };
        const ordered = ordered_columns(columns, { ...layout, hidden: [] }).map((column) => column.fieldname);
        const hidden = new Set(layout.hidden || []);
        const visible = ordered.filter((fieldname) => !hidden.has(fieldname));
        const state = { visible, widths: { ...(layout.widths || {}) }, sticky_end: get_sticky_end(visible, layout.sticky || []) };
        const dialog = new frappe.ui.Dialog({ title: "列设置", fields: [{ fieldname: "columns_html", fieldtype: "HTML" }, ...(can_set_global ? [{ label: "设为全员默认布局", fieldname: "apply_to_all", fieldtype: "Check", description: "勾选后保存为全员默认，并立即应用到当前用户。" }] : [])], primary_action_label: "保存", primary_action(values) {
            const next_layout = { widths: state.widths, order: state.visible, hidden: columns.map((column) => column.fieldname).filter((fieldname) => !state.visible.includes(fieldname)), sticky: get_sticky_fields(state.visible, state.sticky_end) };
            const apply_to_all = Boolean(values?.apply_to_all || dialog.get_value("apply_to_all"));
            const method = apply_to_all ? SET_GLOBAL_LAYOUT_METHOD : SET_MY_LAYOUT_METHOD;
            frappe.call({ method, args: { report_name, layout: next_layout } }).then((response) => {
                if (response.exc) throw new Error(response.exc);
                report._dyeing_finishing_report_layout = response.message || next_layout;
                dialog.hide();
                report.refresh();
                frappe.show_alert({ message: apply_to_all ? "全员默认布局已保存，并已应用到当前用户" : "我的列设置已保存", indicator: "green" });
            }).catch((error) => {
                frappe.msgprint({ title: "列设置保存失败", message: error.message || "无法保存列设置。", indicator: "red" });
            });
        }});
        dialog.set_secondary_action_label("恢复我的默认布局");
        dialog.set_secondary_action(() => { frappe.call({ method: CLEAR_MY_LAYOUT_METHOD, args: { report_name } }).then((response) => { report._dyeing_finishing_report_layout = response.message || { widths: {}, order: [], hidden: [], sticky: [] }; dialog.hide(); report.refresh(); frappe.show_alert({ message: "已恢复默认布局", indicator: "green" }); }); });
        dialog.show();
        render_rows(dialog, columns, state);
    }

    window.dyeing_finishing_report_layout = { register({ report_name, filters = [], onload, after_datatable_render, datatable_options = {} }) {
        let current_report;
        frappe.query_reports[report_name] = { filters, onload(report) {
            current_report = report;
            // ERPNext reuses the query-report Desk page. Remove custom report
            // extensions owned by a different report before rendering this one.
            const page_main = $(report.page?.main || []);
            page_main.find("[data-dyeing-report-owner]").filter((_, element) =>
                element.dataset.dyeingReportOwner !== report_name
            ).remove();
            page_main.find(".report-wrapper").off(".production-progress-master");
            $(report.page?.wrapper || []).addClass("dyeing-finishing-striped-report");
            if (onload) onload(report);
            report.page.add_menu_item("列设置", () => show_layout_dialog(report, report_name, report._dyeing_finishing_can_set_global_layout));
            // Frappe waits for onload before its first refresh; loading the layout here
            // avoids a second refresh and applies columns on the initial render.
            return frappe.call({ method: GET_LAYOUT_METHOD, args: { report_name } }).then((response) => {
                const result = response.message || {};
                report._dyeing_finishing_report_layout = result.layout || { widths: {}, order: [], hidden: [], sticky: [] };
                report._dyeing_finishing_can_set_global_layout = result.can_set_global;
            });
        }, get_datatable_options(options) {
            Object.assign(options, datatable_options);
            const layout = current_report?._dyeing_finishing_report_layout;
            if (layout) options.columns = configured_columns(options.columns || [], layout);
            return options;
        }, after_datatable_render(datatable) {
            $(datatable?.wrapper || []).addClass("dyeing-finishing-striped-report");
            // Frappe refreshes an existing DataTable with raw report columns. Apply
            // the saved layout to that single refresh instead of rendering twice.
            if (datatable && !datatable._dyeing_finishing_layout_refresh) {
                const original_refresh = datatable.refresh;
                datatable.refresh = function (data, columns) {
                    const layout = current_report?._dyeing_finishing_report_layout;
                    return original_refresh.call(this, data, columns && layout ? configured_columns(columns, layout) : columns);
                };
                datatable._dyeing_finishing_layout_refresh = true;
            }
            if (current_report) apply_layout(current_report, datatable);
            if (after_datatable_render && current_report) after_datatable_render(current_report, datatable);
        } };
    }};
})();
