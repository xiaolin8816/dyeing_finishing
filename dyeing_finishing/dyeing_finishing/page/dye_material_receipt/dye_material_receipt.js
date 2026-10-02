frappe.pages["dye-material-receipt"].on_page_load = function () {
    frappe.route_options = { custom_dyeing_receipt_type: "染料/助剂入库" };
    frappe.set_route("List", "Purchase Receipt", "List");
};
