(() => {
    const VERSION_WIDTH = 72;
    const FIELD_ORDER = [
        "recipe_no",
        "customer_name",
        "finished_product_name",
        "color_no",
        "color",
        "recipe_status",
        "recipe_version",
        "sampling_date",
        "name",
    ];

    function order_columns(listview) {
        const columns_by_field = new Map(
            listview.columns
                .filter((column) => column.df?.fieldname)
                .map((column) => [column.df.fieldname, column])
        );
        const subject = listview.columns.find((column) => column.type === "Subject");
        const tag = listview.columns.find((column) => column.type === "Tag");
        const ordered_fields = FIELD_ORDER
            .filter((fieldname) => fieldname !== "recipe_no")
            .map((fieldname) => columns_by_field.get(fieldname))
            .filter(Boolean);

        listview.columns = [subject, tag, ...ordered_fields].filter(Boolean);
    }

    function apply_current_month_filter(listview) {
        if (listview.__laboratory_recipe_default_filter_applied || listview.filter_area.get().length) {
            return;
        }

        listview.__laboratory_recipe_default_filter_applied = true;
        listview.filter_area.add(
            listview.doctype,
            "sampling_date",
            "between",
            [frappe.datetime.month_start(), frappe.datetime.month_end()]
        );
    }

    function apply_recipe_version_width(listview) {
        const width = `${VERSION_WIDTH}px`;
        listview.$result.find('[data-fieldname="recipe_version"]').css({
            width,
            minWidth: width,
            maxWidth: width,
            flex: `0 0 ${width}`,
        });
    }

    frappe.listview_settings["Laboratory Recipe"] = {
        onload(listview) {
            order_columns(listview);
            apply_current_month_filter(listview);
        },
        refresh(listview) {
            order_columns(listview);
            window.setTimeout(() => apply_recipe_version_width(listview), 0);
        },
    };
})();
