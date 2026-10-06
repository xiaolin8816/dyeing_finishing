(() => {
    const VERSION_WIDTH = 72;
    const FIELD_ORDER = [
        "recipe_no",
        "finished_product_name",
        "customer_name",
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

    function has_active_filter(listview) {
        return listview.filter_area.get().some((filter) => {
            const value = filter[3];
            return Array.isArray(value) ? value.some(Boolean) : Boolean(value);
        });
    }

    function apply_current_month_filter(listview) {
        if (listview.__laboratory_recipe_default_filter_applied || has_active_filter(listview)) {
            return;
        }

        const sampling_date = listview.page.fields_dict.sampling_date;
        if (!sampling_date) {
            return;
        }

        listview.__laboratory_recipe_default_filter_applied = true;
        sampling_date.set_value([
            frappe.datetime.month_start(),
            frappe.datetime.month_end(),
        ]);
    }

    function hide_unused_top_filters(listview) {
        listview.page.fields_dict.recipe_no?.$wrapper?.hide();
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
        hide_name_filter: true,
        custom_filter_configs: [
            {
                fieldname: "sampling_date",
                label: "打样日期",
                fieldtype: "DateRange",
                condition: "between",
            },
            {
                fieldname: "color_no",
                label: "色号",
                fieldtype: "Link",
                options: "Color Master",
                condition: "=",
            },
            {
                fieldname: "customer_name",
                label: "客户名称",
                fieldtype: "Data",
                condition: "like",
            },
        ],
        onload(listview) {
            order_columns(listview);
            hide_unused_top_filters(listview);
            apply_current_month_filter(listview);
        },
        refresh(listview) {
            order_columns(listview);
            window.setTimeout(() => apply_recipe_version_width(listview), 0);
        },
    };
})();
