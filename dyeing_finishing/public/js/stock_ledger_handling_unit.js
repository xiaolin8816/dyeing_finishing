(() => {
    function hide_handling_unit_column() {
        const report = frappe.query_report;
        if (!report || report.report_name !== "Stock Ledger" || !report.report_settings || report._dyeing_handling_unit_hidden) return false;

        const original_after_render = report.report_settings.after_datatable_render;
        report.report_settings.after_datatable_render = (datatable) => {
            if (original_after_render) original_after_render(datatable);
            const columns = datatable?.options?.columns || [];
            const visible_columns = columns.filter((column) => column.fieldname !== "handling_unit");
            if (visible_columns.length !== columns.length) {
                datatable.refresh(datatable.options.data, visible_columns);
            }
        };
        report._dyeing_handling_unit_hidden = true;
        report.refresh();
        return true;
    }

    frappe.router.on("change", () => {
        let attempts = 0;
        const timer = setInterval(() => {
            attempts += 1;
            if (hide_handling_unit_column() || attempts >= 12) clearInterval(timer);
        }, 250);
    });
})();
