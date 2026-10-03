/* eslint-disable */
(() => {
    const GET_LAYOUT_METHOD = "dyeing_finishing.dyeing_finishing.list_layout.get_list_layout";
    const SET_MY_LAYOUT_METHOD = "dyeing_finishing.dyeing_finishing.list_layout.set_my_list_layout";
    const CLEAR_MY_LAYOUT_METHOD = "dyeing_finishing.dyeing_finishing.list_layout.clear_my_list_layout";
    const SET_GLOBAL_LAYOUT_METHOD = "dyeing_finishing.dyeing_finishing.list_layout.set_global_list_layout";
    const MIN_WIDTH = 20;
    const MAX_WIDTH = 600;
    const SUPPORTED_DOCTYPES = new Set(["Production Flow Card", "Dye Material Other Issue"]);

    const fieldname_of = (column) => column.type === "Status" ? "__status" : column.df?.fieldname;
    const column_label = (column) => column.type === "Status" ? "状态" : (column.df?.label || column.df?.fieldname);

    function base_columns(listview) {
        if (!listview.__dyeing_finishing_base_columns && (listview.columns || []).length) {
            listview.__dyeing_finishing_base_columns = (listview.columns || []).filter((column) => ["Status", "Subject", "Field"].includes(column.type) && fieldname_of(column));
        }
        return listview.__dyeing_finishing_base_columns || [];
    }

    function get_columns(listview) {
        return base_columns(listview).map((column) => ({ fieldname: fieldname_of(column), label: column_label(column), column }));
    }

    function ordered_columns(listview, layout) {
        const positions = new Map((layout.order || []).map((fieldname, index) => [fieldname, index]));
        const hidden = new Set(layout.hidden || []);
        return base_columns(listview).map((column, original_index) => ({ column, original_index, fieldname: fieldname_of(column) }))
            .filter((item) => !hidden.has(item.fieldname))
            .sort((left, right) => (positions.has(left.fieldname) ? positions.get(left.fieldname) : 10000 + left.original_index) - (positions.has(right.fieldname) ? positions.get(right.fieldname) : 10000 + right.original_index))
            .map((item) => item.column);
    }

    function same_columns(left, right) {
        return left.length === right.length && left.every((column, index) => fieldname_of(column) === fieldname_of(right[index]));
    }

    function status_elements(listview) {
        const status_index = (listview.columns || []).findIndex((column) => column.type === "Status");
        const $body = listview.$result.find(".list-row:not(.list-row-head) .list-row-col").filter((_, element) => $(element).find(".indicator-pill, .indicator").length).first();
        const $header = listview.$result.find(".list-row-head .list-header-subject > .list-row-col").eq(status_index);
        return $body.add($header);
    }

    function elements_for(listview, fieldname) {
        return fieldname === "__status" ? status_elements(listview) : listview.$result.find(`.list-row-col[data-fieldname="${fieldname}"]`);
    }

    function set_fixed_width($columns, width) {
        $columns.css({ width, minWidth: width, maxWidth: width, flex: `0 0 ${width}px` });
    }

    function sync_header_widths(listview) {
        get_columns(listview).forEach(({ fieldname }) => {
            const $columns = elements_for(listview, fieldname);
            const $body = $columns.filter(".list-row:not(.list-row-head) .list-row-col").first();
            const width = $body.outerWidth();
            if (!width) return;
            const $header = fieldname === "__status"
                ? listview.$result.find(".list-row-head .list-header-subject > .list-row-col").eq((listview.columns || []).findIndex((column) => column.type === "Status"))
                : listview.$result.find(`.list-row-head .list-row-col[data-fieldname="${fieldname}"]`);
            set_fixed_width($header, width);
            if (fieldname === "__status") $header.find("> span").toggleClass("d-none", width < 48);
        });
    }

    function apply_sticky_columns(listview, layout) {
        listview.$result.find(".list-row-col").css({ position: "", left: "", zIndex: "", background: "" });
        let left = 0;
        const sticky = new Set(layout.sticky || []);
        get_columns(listview).forEach(({ fieldname }) => {
            if (!sticky.has(fieldname)) return;
            const $columns = elements_for(listview, fieldname);
            const width = $columns.filter(".list-row:not(.list-row-head) .list-row-col").first().outerWidth();
            if (!width) return;
            $columns.css({ position: "sticky", left: `${left}px`, zIndex: 2, background: "var(--card-bg, #fff)" });
            listview.$result.find(".list-row-head .list-row-col").filter((_, element) => $(element).is($columns)).css({ zIndex: 3, background: "var(--card-bg, #fff)" });
            left += width;
        });
    }

    function apply_layout(listview) {
        const layout = listview.__dyeing_finishing_list_layout || { widths: {}, order: [], hidden: [], sticky: [] };
        const expected = ordered_columns(listview, layout);
        if (!same_columns(listview.columns || [], expected)) {
            listview.columns = expected;
            listview.refresh();
            return;
        }
        Object.entries(layout.widths || {}).forEach(([fieldname, width]) => {
            const value = Number(width);
            if (Number.isFinite(value) && value >= MIN_WIDTH) set_fixed_width(elements_for(listview, fieldname), value);
        });
        window.setTimeout(() => { sync_header_widths(listview); apply_sticky_columns(listview, layout); }, 0);
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
            return `<div class="sortable list-layout-row border rounded mb-2 px-2 py-1" data-fieldname="${fieldname}"><div class="row align-items-center"><div class="col-1 d-flex justify-content-center sortable-handle" style="cursor: grab;">${frappe.utils.icon("drag", "xs")}</div><div class="col-5">${escape_html(column.label)}</div><div class="col-2"><input class="form-control form-control-sm list-layout-width" type="number" min="${MIN_WIDTH}" max="${MAX_WIDTH}" value="${state.widths[fieldname] || ""}" data-fieldname="${fieldname}"></div><div class="col-2 text-center"><input class="list-layout-sticky" type="checkbox" data-fieldname="${fieldname}" ${state.sticky.has(fieldname) ? "checked" : ""}></div><div class="col-2 text-center"><a class="text-muted list-layout-remove" data-fieldname="${fieldname}" title="隐藏字段">${frappe.utils.icon("trash", "xs")}</a></div></div></div>`;
        }).join("");
        const wrapper = dialog.get_field("columns_html").$wrapper;
        wrapper.html(`<div class="row text-muted mb-2"><div class="col-1"></div><div class="col-5">字段名</div><div class="col-2">宽度</div><div class="col-2 text-center">置顶</div><div class="col-2"></div></div><div class="list-layout-rows">${rows}</div><a class="text-muted list-layout-select-fields">+ 添加/移除列</a>`);
        new Sortable(wrapper.find(".list-layout-rows")[0], { handle: ".sortable-handle", draggable: ".sortable", animation: 150, onUpdate: () => { state.visible = wrapper.find(".list-layout-row").map((_, row) => row.dataset.fieldname).get(); } });
        wrapper.find(".list-layout-width").on("change", (event) => { state.widths[event.target.dataset.fieldname] = Number(event.target.value) || ""; });
        wrapper.find(".list-layout-sticky").on("change", (event) => { event.target.checked ? state.sticky.add(event.target.dataset.fieldname) : state.sticky.delete(event.target.dataset.fieldname); });
        wrapper.find(".list-layout-remove").on("click", (event) => { const fieldname = event.currentTarget.dataset.fieldname; state.visible = state.visible.filter((item) => item !== fieldname); state.sticky.delete(fieldname); render_rows(dialog, columns, state); });
        wrapper.find(".list-layout-select-fields").on("click", () => show_column_selector(dialog, columns, state));
    }

    function show_column_selector(parent_dialog, columns, state) {
        const selected = new Set(state.visible);
        const selector = new frappe.ui.Dialog({ title: "添加/移除列", fields: columns.map((column) => ({ label: column.label, fieldname: `show_${column.fieldname}`, fieldtype: "Check", default: selected.has(column.fieldname) ? 1 : 0 })), primary_action_label: "确定", primary_action(values) {
            const next_visible = columns.filter((column) => values[`show_${column.fieldname}`]).map((column) => column.fieldname);
            if (!next_visible.length) { frappe.msgprint("请至少保留一个字段。"); return; }
            state.visible = state.visible.filter((fieldname) => next_visible.includes(fieldname));
            next_visible.forEach((fieldname) => { if (!state.visible.includes(fieldname)) state.visible.push(fieldname); });
            state.sticky = new Set([...state.sticky].filter((fieldname) => state.visible.includes(fieldname)));
            selector.hide(); render_rows(parent_dialog, columns, state);
        } });
        selector.show();
    }

    function show_layout_dialog(listview, doctype, can_set_global) {
        const columns = get_columns(listview);
        if (!columns.length) { frappe.msgprint("请先等待列表数据加载完成，再调整列设置。"); return; }
        const layout = listview.__dyeing_finishing_list_layout || { widths: {}, order: [], hidden: [], sticky: [] };
        const positions = new Map((layout.order || []).map((fieldname, index) => [fieldname, index]));
        const order = [...columns].sort((left, right) => (positions.has(left.fieldname) ? positions.get(left.fieldname) : 10000) - (positions.has(right.fieldname) ? positions.get(right.fieldname) : 10000)).map((column) => column.fieldname);
        const hidden = new Set(layout.hidden || []);
        const state = { visible: order.filter((fieldname) => !hidden.has(fieldname)), widths: { ...(layout.widths || {}) }, sticky: new Set(layout.sticky || []) };
        const dialog = new frappe.ui.Dialog({ title: "列设置", fields: [{ fieldname: "columns_html", fieldtype: "HTML" }, ...(can_set_global ? [{ label: "设为全员默认布局", fieldname: "apply_to_all", fieldtype: "Check", default: 1, description: "勾选后，未设置个人布局的用户将使用此布局。" }] : [])], primary_action_label: "保存", primary_action(values) {
            const next_layout = { widths: state.widths, order: state.visible, hidden: columns.map((column) => column.fieldname).filter((fieldname) => !state.visible.includes(fieldname)), sticky: [...state.sticky] };
            const method = values.apply_to_all ? SET_GLOBAL_LAYOUT_METHOD : SET_MY_LAYOUT_METHOD;
            frappe.call({ method, args: { doctype, layout: next_layout } }).then((response) => { listview.__dyeing_finishing_list_layout = response.message || next_layout; dialog.hide(); apply_layout(listview); frappe.show_alert({ message: values.apply_to_all ? "已设为全员默认布局" : "我的列设置已保存", indicator: "green" }); });
        } });
        dialog.set_secondary_action_label("恢复我的默认布局");
        dialog.set_secondary_action(() => { frappe.call({ method: CLEAR_MY_LAYOUT_METHOD, args: { doctype } }).then((response) => { listview.__dyeing_finishing_list_layout = response.message || { widths: {}, order: [], hidden: [], sticky: [] }; dialog.hide(); apply_layout(listview); frappe.show_alert({ message: "已恢复默认布局", indicator: "green" }); }); });
        dialog.show(); render_rows(dialog, columns, state);
    }

    function setup_list_layout(doctype) {
        const existing = frappe.listview_settings[doctype] || {};
        frappe.listview_settings[doctype] = {
            ...existing,
            onload(listview) {
                if (existing.onload) existing.onload(listview);
                frappe.call({ method: GET_LAYOUT_METHOD, args: { doctype } }).then((response) => {
                    const result = response.message || {};
                    listview.__dyeing_finishing_list_layout = result.layout || { widths: {}, order: [], hidden: [], sticky: [] };
                    listview.__dyeing_finishing_can_set_global_layout = result.can_set_global;
                    apply_layout(listview);
                });
            },
            refresh(listview) {
                if (existing.refresh) existing.refresh(listview);
                window.setTimeout(() => apply_layout(listview), 0);
            },
        };
    }

    SUPPORTED_DOCTYPES.forEach(setup_list_layout);

    const ListView = frappe.views?.ListView;
    if (ListView && !ListView.prototype.__dyeing_finishing_list_layout_override) {
        const original_get_view_settings = ListView.prototype.get_view_settings;
        ListView.prototype.get_view_settings = function() {
            if (!SUPPORTED_DOCTYPES.has(this.doctype)) return original_get_view_settings.call(this);
            return {
                label: __("List Settings", null, "Button in list view menu"),
                action: () => show_layout_dialog(this, this.doctype, true),
                standard: true,
            };
        };
        ListView.prototype.__dyeing_finishing_list_layout_override = true;
    }
})();
