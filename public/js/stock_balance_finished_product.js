(() => {
  const add_finished_product_stock_button = () => {
    const route = frappe.get_route();
    if (route[0] !== "query-report" || route[1] !== "Stock Balance" || !frappe.query_report?.page) return;
    if (frappe.query_report.page.__finished_product_stock_button) return;
    frappe.query_report.page.__finished_product_stock_button = true;
    frappe.query_report.page.add_inner_button(__("Finished Product Stock"), () => {
      const filters = frappe.query_report.get_filter_values?.() || {};
      frappe.set_route("query-report", "Finished Product Stock", {
        company: filters.company,
        warehouse: Array.isArray(filters.warehouse) ? filters.warehouse[0] : filters.warehouse,
      });
    });
  };

  frappe.router.on("change", () => setTimeout(add_finished_product_stock_button, 500));
  frappe.after_ajax(() => setTimeout(add_finished_product_stock_button, 200));
})();
