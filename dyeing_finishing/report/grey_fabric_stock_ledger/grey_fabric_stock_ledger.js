dyeing_finishing_report_layout.register({
    report_name: "Grey Fabric Stock Ledger",
    filters: [
        { fieldname: "from_date", label: __("开始日期"), fieldtype: "Date", default: frappe.datetime.add_months(frappe.datetime.get_today(), -1), reqd: 1 },
        { fieldname: "to_date", label: __("结束日期"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
        {
            fieldname: "warehouse", label: __("仓库"), fieldtype: "Link", options: "Warehouse",
            get_query: () => ({ filters: { company: frappe.query_report.get_filter_value("company") } }),
        },
        { fieldname: "customer", label: __("客户"), fieldtype: "Link", options: "Customer" },
        { fieldname: "batch_no", label: __("匹号/批次"), fieldtype: "Link", options: "Batch" },
        { fieldname: "item_code", label: __("胚布"), fieldtype: "Link", options: "Item" },
        {
            fieldname: "group_by", label: __("分组方式"), fieldtype: "Select",
            options: "客户+匹号+仓库\n仓库+匹号\n不分组", default: "客户+匹号+仓库",
        },
        { fieldname: "sort_order", label: __("排序"), fieldtype: "Select", options: "记账顺序\n最新优先", default: "记账顺序" },
        { fieldname: "company", label: __("公司"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company") },
        { fieldname: "include_child_warehouses", label: __("包含下级仓库"), fieldtype: "Check", default: 1, depends_on: "eval:doc.warehouse" },
        { fieldname: "movement_type", label: __("流水类型"), fieldtype: "Select", options: "\n收入\n发出\n报损\n盘点调整\n过户\n其他" },
        {
            fieldname: "business_type", label: __("业务类型"), fieldtype: "Select",
            options: "\n客户胚布入库\n胚布出库\n胚布报损\n仓库调拨\n胚布过户\n客户胚布退货\n胚布盘点\n成品退货转胚布\n成品库存转胚布\n其他库存变动",
        },
        { fieldname: "business_document", label: __("业务单号"), fieldtype: "Data" },
        { fieldname: "show_opening", label: __("显示期初"), fieldtype: "Check", default: 1 },
        { fieldname: "show_zero_balance", label: __("显示期末为零"), fieldtype: "Check", default: 1 },
    ],
    onload(report) {
        report.page_title = "胚布收发存流水";
        report.page.set_title(report.page_title);
        const $summary = report.$summary?.length
            ? report.$summary
            : $(report.page.main).find(".report-summary");
        $summary.attr("data-grey-fabric-stock-ledger-summary", "1");
        if (!document.getElementById("grey-fabric-stock-ledger-row-styles")) {
            $("<style>", {
                id: "grey-fabric-stock-ledger-row-styles",
                text: `
                    .report-summary[data-grey-fabric-stock-ledger-summary="1"] {
                        flex-wrap: nowrap;
                        justify-content: flex-start;
                        gap: 6px;
                        margin: 6px 15px;
                        padding: 6px 8px;
                        overflow-x: auto;
                        overflow-y: hidden;
                    }
                    .report-summary[data-grey-fabric-stock-ledger-summary="1"] .summary-item {
                        flex: 1 0 108px;
                        min-width: 108px;
                        max-width: none;
                        height: 46px;
                        margin: 0 3px;
                    }
                    .report-summary[data-grey-fabric-stock-ledger-summary="1"] .summary-label {
                        font-size: 12px;
                        line-height: 16px;
                    }
                    .report-summary[data-grey-fabric-stock-ledger-summary="1"] .summary-value {
                        font-size: 16px;
                        line-height: 16px;
                        padding-top: 4px;
                        padding-bottom: 2px;
                    }
                    .dt-cell:has(.grey-ledger-opening-cell) {
                        background: #f4f6f9 !important;
                        color: #475569;
                    }
                    .dt-cell:has(.grey-ledger-subtotal-cell) {
                        background: #eaf7fa !important;
                        border-top: 1px solid #c9e7ec !important;
                        border-bottom: 1px solid #c9e7ec !important;
                        font-weight: 600;
                    }
                `,
            }).appendTo(document.head);
        }
    },
});

Object.assign(frappe.query_reports["Grey Fabric Stock Ledger"], {
    collapsible_filters: true,
    separate_check_filters: true,
});

frappe.query_reports["Grey Fabric Stock Ledger"].formatter = function (value, row, column, data, default_formatter) {
    const formatted = default_formatter(value, row, column, data);
    if (data?.row_type === "opening") {
        return `<span class="grey-ledger-opening-cell">${formatted}</span>`;
    }
    if (data?.row_type === "subtotal") {
        return `<span class="grey-ledger-subtotal-cell">${formatted}</span>`;
    }
    return formatted;
};
