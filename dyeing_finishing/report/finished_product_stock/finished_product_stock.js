frappe.query_reports["Finished Product Stock"] = {
  filters: [
    {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_default("company")},
    {fieldname: "warehouse", label: __("Warehouse"), fieldtype: "Link", options: "Warehouse"},
    {fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer"},
    {fieldname: "item_code", label: __("Item"), fieldtype: "Link", options: "Item"},
    {fieldname: "batch_no", label: __("Batch No"), fieldtype: "Link", options: "Batch"},
    {fieldname: "production_flow_card", label: __("Production Flow Card"), fieldtype: "Link", options: "Production Flow Card"},
    {fieldname: "show_zero_stock", label: __("Show Zero Stock"), fieldtype: "Check", default: 0},
  ],
};

dyeing_finishing_report_layout.register({report_name: "Finished Product Stock"});
