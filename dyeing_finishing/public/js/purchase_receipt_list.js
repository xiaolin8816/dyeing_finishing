frappe.listview_settings["Purchase Receipt"] = {
    onload(listview) {
        listview.page.add_inner_button("染料入库单", () => {
            frappe.route_options = { custom_dyeing_receipt_type: "染料/助剂入库" };
            frappe.set_route("List", "Purchase Receipt", "List");
        }, "染料管理");
        listview.page.add_inner_button("新建染料入库单", () => {
            frappe.new_doc("Purchase Receipt", { custom_dyeing_receipt_type: "染料/助剂入库" });
        }, "染料管理");
    },
};
