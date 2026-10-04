dyeing_finishing_report_layout.register({
    report_name: "Dye Material Return Register",
    filters: [
        { fieldname: "from_date", label: "退货日期起", fieldtype: "Date", default: frappe.datetime.month_start() },
        { fieldname: "to_date", label: "退货日期止", fieldtype: "Date", default: frappe.datetime.month_end() },
        { fieldname: "supplier", label: "供应商", fieldtype: "Link", options: "Supplier" },
        { fieldname: "source_warehouse", label: "退货仓库", fieldtype: "Link", options: "Warehouse" },
        { fieldname: "return_reason", label: "退货原因", fieldtype: "Select", options: "\n质量不合格\n数量错误\n包装破损\n临期\n其他" },
        { fieldname: "status", label: "状态", fieldtype: "Select", options: "\n保存\n已提交" },
    ],
    onload(report) {
        const title = "染料退货记录";
        report.page.set_title(title);
        frappe.utils.set_title(title);
        report.page.add_inner_button("新建染料退货单", () => frappe.new_doc("Dye Material Return"));
    },
});
