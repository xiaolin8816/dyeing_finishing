const DYEING_RECEIPT_TYPE = "染料/助剂入库";
const ROOT_WORKSPACE = "印染整理";
const SHARED_ROUTE_CONTEXT_KEY = "dyeing_finishing.shared_route_owner";
const purchaseReceiptListSettings = frappe.listview_settings["Purchase Receipt"] || {};
const originalOnload = purchaseReceiptListSettings.onload;

function isDyeingReceiptEntry() {
    return frappe.app?.sidebar?.sidebar_title === ROOT_WORKSPACE
        || window.sessionStorage.getItem(SHARED_ROUTE_CONTEXT_KEY) === "purchase receipt";
}

frappe.listview_settings["Purchase Receipt"] = {
    ...purchaseReceiptListSettings,
    onload(listview) {
        originalOnload?.(listview);

        if (listview.dyeingReceiptFilterApplied) return;
        listview.dyeingReceiptFilterApplied = true;

        const dyeingEntry = isDyeingReceiptEntry();
        const result = listview.filter_area.add(
            "Purchase Receipt",
            "custom_dyeing_receipt_type",
            dyeingEntry ? "=" : "!=",
            DYEING_RECEIPT_TYPE,
            true,
        );
        if (result?.then) {
            result.then(() => listview.refresh());
        }
        if (dyeingEntry) {
            window.sessionStorage.setItem(SHARED_ROUTE_CONTEXT_KEY, "purchase receipt");
            listview.page.set_primary_action(__("新建染料采购入库单"), () => {
                window.sessionStorage.setItem(SHARED_ROUTE_CONTEXT_KEY, "purchase receipt");
                frappe.new_doc("Purchase Receipt", {custom_dyeing_receipt_type: DYEING_RECEIPT_TYPE});
            });
        }
    },
};
