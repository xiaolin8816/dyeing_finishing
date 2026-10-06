dyeing_finishing_report_layout.register({
    report_name: "Dye Material Stock",
    filters: [
        { fieldname: "warehouse", label: "仓库", fieldtype: "Link", options: "Warehouse", default: "染料仓库 - 沅泰", reqd: 1 },
        { fieldname: "material_category", label: "类别", fieldtype: "Select", options: "\n染料\n助剂" },
        { fieldname: "item_code", label: "物料编码", fieldtype: "Link", options: "Item" },
        { fieldname: "include_zero_stock", label: "显示零库存", fieldtype: "Check", default: 0 },
    ],
    onload(report) {
        const title = "染料库存";
        report.page.set_title(title);
        frappe.utils.set_title(title);
        report.page.add_inner_button("查看库存流水", () => {
            frappe.set_route("query-report", "Stock Ledger", {
                warehouse: report.get_filter_value("warehouse"),
                item_code: report.get_filter_value("item_code"),
            });
        });
    },
});