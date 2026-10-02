frappe.query_reports["Dye Material Receipt Register"] = {
    filters: [
        {
            fieldname: "from_date",
            label: "入库日期起",
            fieldtype: "Date",
            default: frappe.datetime.month_start(),
        },
        {
            fieldname: "to_date",
            label: "入库日期止",
            fieldtype: "Date",
            default: frappe.datetime.month_end(),
        },
        {
            fieldname: "supplier",
            label: "供应商",
            fieldtype: "Link",
            options: "Supplier",
        },
    ],
    onload(report) {
        const title = "染料入库记录";
        report.page.set_title(title);
        frappe.utils.set_title(title);
        report.page.add_inner_button("新建染料入库单", () => {
            frappe.new_doc("Purchase Receipt", {
                custom_dyeing_receipt_type: "染料/助剂入库",
            });
        });
    },
};
