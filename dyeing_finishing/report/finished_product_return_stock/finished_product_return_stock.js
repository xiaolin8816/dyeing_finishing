frappe.query_reports["Finished Product Return Stock"] = {
  filters: [
    {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_default("company")},
    {fieldname: "warehouse", label: __("退货待检仓"), fieldtype: "Link", options: "Warehouse"},
    {fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer"},
    {fieldname: "production_flow_card", label: __("Production Flow Card"), fieldtype: "Link", options: "Production Flow Card"},
    {fieldname: "return_document", label: __("成品退货处理单"), fieldtype: "Link", options: "Finished Product Return"},
    {fieldname: "return_reason", label: __("退货原因"), fieldtype: "Select", options: "\n色差\n手感\n门幅\n克重\n缩水\n疵点\n包装\n数量差异\n其他"},
    {fieldname: "inspection_status", label: __("检验状态"), fieldtype: "Select", options: "\n待检\n已检验"},
    {fieldname: "from_date", label: __("From Date"), fieldtype: "Date"},
    {fieldname: "to_date", label: __("To Date"), fieldtype: "Date"},
  ],
};

dyeing_finishing_report_layout.register({report_name: "Finished Product Return Stock"});
