(() => {
    const CONTEXT_KEY = "dyeing_finishing.shared_route_owner";
    const PROFILE_KEY = "dyeing_finishing.item_profile";
    const ROOT_WORKSPACE = "印染整理";
    const settings = frappe.listview_settings["Item"] || {};
    const original_onload = settings.onload;
    const original_refresh = settings.refresh;

    function requested_profile() {
        const filter = new URLSearchParams(window.location.search).get("item_group") || "";
        if (filter.includes("成品")) return "finished_product";
        if (filter.includes("染料") && filter.includes("助剂")) return "dyeing_material";
        return frappe.app?.sidebar?.sidebar_title === ROOT_WORKSPACE
            ? window.sessionStorage.getItem(PROFILE_KEY) || ""
            : "";
    }

    function configure_item_list(listview) {
        const profile = requested_profile();
        if (!profile) return;
        window.sessionStorage.setItem(CONTEXT_KEY, "item");
        window.sessionStorage.setItem(PROFILE_KEY, profile);
        listview.show_list_settings = async () => {
            let open_settings = frappe.dyeing_finishing?.open_list_layout_settings;
            if (!open_settings) {
                try {
                    await $.ajax({url: "/assets/dyeing_finishing/js/list_layout.js?v=20261007-1", dataType: "script", cache: true});
                } catch (error) {
                    console.error(error);
                }
                open_settings = frappe.dyeing_finishing?.open_list_layout_settings;
            }
            if (!open_settings) {
                frappe.msgprint(__("统一列表设置加载失败，请联系管理员检查页面错误日志。"));
                return;
            }
            open_settings(listview, profile === "finished_product" ? "Finished Product Item" : "Dyeing Material Item");
        };
        listview.page.set_primary_action(
            profile === "finished_product" ? __("新建成品物料") : __("新建染料物料"),
            () => frappe.new_doc("Item", profile === "finished_product" ? {
                custom_is_finished_product: 1,
                item_group: "成品",
                stock_uom: "Kg",
                is_stock_item: 1,
                has_batch_no: 1,
            } : {
                custom_is_dyeing_material: 1,
                item_group: "染料",
                stock_uom: "Kg",
                is_stock_item: 1,
            })
        );
    }

    settings.onload = function (listview) {
        original_onload?.call(this, listview);
        listview.page.main.parent().addClass("dyeing-item-list");
        configure_item_list(listview);
    };

    settings.refresh = function (listview) {
        original_refresh?.call(this, listview);
        configure_item_list(listview);
    };

    frappe.listview_settings["Item"] = settings;
})();
