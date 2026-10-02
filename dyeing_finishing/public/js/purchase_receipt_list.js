const DYEING_RECEIPT_TYPE = "染料/助剂入库";
const purchaseReceiptListSettings = frappe.listview_settings["Purchase Receipt"] || {};
const originalOnload = purchaseReceiptListSettings.onload;

frappe.listview_settings["Purchase Receipt"] = {
    ...purchaseReceiptListSettings,
    onload(listview) {
        originalOnload?.(listview);

        if (listview.dyeingReceiptFilterApplied) return;
        listview.dyeingReceiptFilterApplied = true;

        const result = listview.filter_area.add(
            "Purchase Receipt",
            "custom_dyeing_receipt_type",
            "!=",
            DYEING_RECEIPT_TYPE,
            true,
        );
        if (result?.then) {
            result.then(() => listview.refresh());
        }
    },
};
