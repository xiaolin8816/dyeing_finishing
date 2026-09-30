(() => {
    const DOCTYPE = "Production Flow Card";
    const GET_WIDTHS_METHOD = "dyeing_finishing.dyeing_finishing.doctype.production_flow_card.production_flow_card.get_production_flow_card_list_column_widths";
    const SET_WIDTHS_METHOD = "dyeing_finishing.dyeing_finishing.doctype.production_flow_card.production_flow_card.set_production_flow_card_list_column_widths";
    const MIN_WIDTH = 20;
    const MAX_WIDTH = 600;

    function get_columns(listview) {
        return (listview.columns || []).flatMap((column) => {
            if (column.type === "Status") return [{ fieldname: "__status", label: "状态" }];
            if (!["Subject", "Field"].includes(column.type) || !column.df?.fieldname) return [];
            return [{ fieldname: column.df.fieldname, label: column.df.label || column.df.fieldname }];
        });
    }

    function get_widths(listview) {
        return listview.__production_flow_card_column_widths || {};
    }

    function get_status_column_elements(listview) {
        const status_index = (listview.columns || []).findIndex((column) => column.type === "Status");
        const $body_columns = listview.$result
            .find(".list-row-col")
            .filter((_, element) => $(element).find(".indicator-pill, .indicator").length);
        if (status_index < 0) return $body_columns;
        const $header_column = listview.$result
            .find(".list-row-head .list-header-subject > .list-row-col")
            .eq(status_index);
        return $body_columns.add($header_column);
    }

    function set_fixed_width($columns, width) {
        $columns.css({
            width,
            minWidth: width,
            maxWidth: width,
            flex: `0 0 ${width}px`,
        });
    }

    function synchronize_header_widths(listview) {
        get_columns(listview).forEach((column) => {
            const is_status = column.fieldname === "__status";
            const $body_column = is_status
                ? listview.$result.find(".list-row:not(.list-row-head) .list-row-col").filter((_, element) => $(element).find(".indicator-pill, .indicator").length).first()
                : listview.$result.find(`.list-row:not(.list-row-head) .list-row-col[data-fieldname="${column.fieldname}"]`).first();
            const width = $body_column.outerWidth();
            if (!width) return;
            const $header_column = is_status
                ? listview.$result.find(".list-row-head .list-header-subject > .list-row-col").eq((listview.columns || []).findIndex((item) => item.type === "Status"))
                : listview.$result.find(`.list-row-head .list-row-col[data-fieldname="${column.fieldname}"]`);
            set_fixed_width($header_column, width);
            if (is_status) {
                $header_column.find("> span").toggleClass("d-none", width < 48);
            }
        });
    }

    function apply_widths(listview) {
        Object.entries(get_widths(listview)).forEach(([fieldname, width]) => {
            const value = Number(width);
            if (!Number.isFinite(value) || value < MIN_WIDTH) return;
            const $columns = fieldname === "__status"
                ? get_status_column_elements(listview)
                : listview.$result.find(`.list-row-col[data-fieldname="${fieldname}"]`);
            set_fixed_width($columns, value);
        });
        window.setTimeout(() => synchronize_header_widths(listview), 0);
    }

    function load_widths(listview) {
        return frappe.call({ method: GET_WIDTHS_METHOD }).then((response) => {
            listview.__production_flow_card_column_widths = response.message || {};
            apply_widths(listview);
        });
    }

    function show_width_dialog(listview) {
        const columns = get_columns(listview);
        if (!columns.length) {
            frappe.msgprint("当前列表没有可调整宽度的字段。");
            return;
        }
        const widths = get_widths(listview);
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
                    const value = Number(values[`width_${column.fieldname}`]);
                    if (!value) return;
                    if (value < MIN_WIDTH || value > MAX_WIDTH) {
                        has_invalid_width = true;
                        return;
                    }
                    next_widths[column.fieldname] = value;
                });
                if (has_invalid_width) {
                    frappe.msgprint(`列宽应在 ${MIN_WIDTH} 至 ${MAX_WIDTH} 之间。`);
                    return;
                }
                frappe.call({ method: SET_WIDTHS_METHOD, args: { widths: next_widths } }).then((response) => {
                    listview.__production_flow_card_column_widths = response.message || {};
                    apply_widths(listview);
                    dialog.hide();
                    frappe.show_alert({ message: "列表列宽已应用给所有用户", indicator: "green" });
                });
            },
        });
        dialog.set_secondary_action_label("恢复所有用户默认宽度");
        dialog.set_secondary_action(() => {
            frappe.call({ method: SET_WIDTHS_METHOD, args: { widths: {} } }).then(() => {
                listview.__production_flow_card_column_widths = {};
                listview.$result.find(".list-row-col[data-fieldname]").css({ width: "", minWidth: "", maxWidth: "", flex: "" });
                get_status_column_elements(listview).css({ width: "", minWidth: "", maxWidth: "", flex: "" });
                dialog.hide();
                listview.refresh();
            });
        });
        dialog.show();
    }


    frappe.listview_settings[DOCTYPE] = {
        onload(listview) {
            load_widths(listview);
            listview.page.add_menu_item("调整列表列宽", () => show_width_dialog(listview));
        },
        refresh(listview) {
            window.setTimeout(() => apply_widths(listview), 0);
        },
    };
})();
