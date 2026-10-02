const DYEING_RECEIPT_TYPE = "染料/助剂入库";

function setDyeingReceiptListTitle(listview) {
    const isDyeingReceiptList = listview.get_filter_value("custom_dyeing_receipt_type") === DYEING_RECEIPT_TYPE;
    const title = __(isDyeingReceiptList ? "染料入库" : "采购收货单");
    listview.page.set_title(title);
    frappe.utils.set_title(title);
}

frappe.listview_settings["Purchase Receipt"] = {
    onload(listview) {
        const refresh = listview.refresh.bind(listview);
        listview.refresh = (...args) => refresh(...args).then((result) => {
            setDyeingReceiptListTitle(listview);
            return result;
        });
        setDyeingReceiptListTitle(listview);

        listview.page.add_inner_button("染料入库单", () => {
            frappe.route_options = { custom_dyeing_receipt_type: "染料/助剂入库" };
            frappe.set_route("List", "Purchase Receipt", "List");
        }, "染料管理");
        listview.page.add_inner_button("新建染料入库单", () => {
            frappe.new_doc("Purchase Receipt", { custom_dyeing_receipt_type: "染料/助剂入库" });
        }, "染料管理");
    },
};
