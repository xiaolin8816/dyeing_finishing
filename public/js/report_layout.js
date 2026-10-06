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

    function same_column_order(current, expected) {
        return current.length === expected.length && current.every((column, index) => column.fieldname === expected[index].fieldname);
    }

    function apply_layout(report, datatable = report.datatable) {
        if (!datatable) return;
        const layout = report._dyeing_finishing_report_layout || { widths: {}, order: [], hidden: [], sticky: [] };
        const expected_columns = ordered_columns(datatable.options.columns || [], layout);
        if (!same_column_order(datatable.options.columns || [], expected_columns)) {
            datatable.refresh(datatable.options.data, expected_columns);
        }
        const sticky = new Set(layout.sticky || []);
        datatable.getColumns().forEach((column) => {
            const width = Number(layout.widths?.[column.fieldname]);
            const updates = { sticky: sticky.has(column.fieldname) };
            if (Number.isFinite(width) && width >= MIN_WIDTH) updates.width = width;
            datatable.datamanager.updateColumn(column.colIndex, updates);
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
                    <div class="col-5">${escape_html(column.label)}</div>
                    <div class="col-2"><input class="form-control form-control-sm report-layout-width" type="number" min="${MIN_WIDTH}" max="${MAX_WIDTH}" value="${state.widths[fieldname] || ""}" data-fieldname="${fieldname}"></div>
                    <div class="col-2 text-center"><input class="report-layout-sticky" type="checkbox" data-fieldname="${fieldname}" ${state.sticky.has(fieldname) ? "checked" : ""}></div>
                    <div class="col-2 text-center"><a class="text-muted report-layout-remove" data-fieldname="${fieldname}" title="隐藏字段">${frappe.utils.icon("trash", "xs")}</a></div>
                </div>
            </div>`;
        }).join("");
        const wrapper = dialog.get_field("columns_html").$wrapper;
        wrapper.html(`<div class="row text-muted mb-2"><div class="col-1"></div><div class="col-5">字段名</div><div class="col-2">宽度</div><div class="col-2 text-center">置顶</div><div class="col-2"></div></div><div class="report-layout-rows">${rows}</div><a class="text-muted report-layout-select-fields">+ 添加/移除列</a>`);
        new Sortable(wrapper.find(".report-layout-rows")[0], { handle: ".sortable-handle", draggable: ".sortable", animation: 150, onUpdate: () => {
            state.visible = wrapper.find(".report-layout-row").map((_, row) => row.dataset.fieldname).get();
        }});
        wrapper.find(".report-layout-width").on("change", (event) => { state.widths[event.target.dataset.fieldname] = Number(event.target.value) || ""; });
        wrapper.find(".report-layout-sticky").on("change", (event) => { event.target.checked ? state.sticky.add(event.target.dataset.fieldname) : state.sticky.delete(event.target.dataset.fieldname); });
        wrapper.find(".report-layout-remove").on("click", (event) => { const fieldname = event.currentTarget.dataset.fieldname; state.visible = state.visible.filter((item) => item !== fieldname); state.sticky.delete(fieldname); render_rows(dialog, columns, state); });
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
                state.sticky = new Set([...state.sticky].filter((fieldname) => state.visible.includes(fieldname)));
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
        const state = { visible: ordered.filter((fieldname) => !hidden.has(fieldname)), widths: { ...(layout.widths || {}) }, sticky: new Set(layout.sticky || []) };
        const dialog = new frappe.ui.Dialog({ title: "列设置", fields: [{ fieldname: "columns_html", fieldtype: "HTML" }, ...(can_set_global ? [{ label: "设为全员默认布局", fieldname: "apply_to_all", fieldtype: "Check", description: "勾选后，未设置个人布局的用户将使用此布局。" }] : [])], primary_action_label: "保存", primary_action(values) {
            const next_layout = { widths: state.widths, order: state.visible, hidden: columns.map((column) => column.fieldname).filter((fieldname) => !state.visible.includes(fieldname)), sticky: [...state.sticky] };
            const method = values.apply_to_all ? SET_GLOBAL_LAYOUT_METHOD : SET_MY_LAYOUT_METHOD;
            frappe.call({ method, args: { report_name, layout: next_layout } }).then((response) => { report._dyeing_finishing_report_layout = response.message || next_layout; dialog.hide(); report.refresh(); frappe.show_alert({ message: values.apply_to_all ? "已设为全员默认布局" : "我的列设置已保存", indicator: "green" }); });
        }});
        dialog.set_secondary_action_label("恢复我的默认布局");
        dialog.set_secondary_action(() => { frappe.call({ method: CLEAR_MY_LAYOUT_METHOD, args: { report_name } }).then((response) => { report._dyeing_finishing_report_layout = response.message || { widths: {}, order: [], hidden: [], sticky: [] }; dialog.hide(); report.refresh(); frappe.show_alert({ message: "已恢复默认布局", indicator: "green" }); }); });
        dialog.show();
        render_rows(dialog, columns, state);
    }

    window.dyeing_finishing_report_layout = { register({ report_name, filters = [], onload }) {
        let current_report;
        frappe.query_reports[report_name] = { filters, onload(report) {
            current_report = report;
            if (onload) onload(report);
            frappe.call({ method: GET_LAYOUT_METHOD, args: { report_name } }).then((response) => { const result = response.message || {}; report._dyeing_finishing_report_layout = result.layout || { widths: {}, order: [], hidden: [], sticky: [] }; report._dyeing_finishing_can_set_global_layout = result.can_set_global; report.refresh(); });
            report.page.add_menu_item("列设置", () => show_layout_dialog(report, report_name, report._dyeing_finishing_can_set_global_layout));
        }, get_datatable_options(options) { const layout = current_report?._dyeing_finishing_report_layout; if (layout) options.columns = ordered_columns(options.columns || [], layout); return options; }, after_datatable_render(datatable) { if (current_report) apply_layout(current_report, datatable); } };
    }};
})();