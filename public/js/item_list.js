(() => {
    const CONTEXT_KEY = "dyeing_finishing.shared_route_owner";
    const ROOT_WORKSPACE = "印染整理";
    const settings = frappe.listview_settings["Item"] || {};
    const original_onload = settings.onload;
    const original_refresh = settings.refresh;

    function is_dyeing_material_list() {
        const item_group_filter = new URLSearchParams(window.location.search).get("item_group") || "";
        return frappe.app?.sidebar?.sidebar_title === ROOT_WORKSPACE
            || window.sessionStorage.getItem(CONTEXT_KEY) === "item"
            || (item_group_filter.includes("染料") && item_group_filter.includes("助剂"));
    }

    function configure_dyeing_material_list(listview) {
        if (!is_dyeing_material_list()) return;

        window.sessionStorage.setItem(CONTEXT_KEY, "item");
        listview.show_list_settings = async () => {
            let open_settings = frappe.dyeing_finishing?.open_list_layout_settings;
            if (!open_settings) {
                try {
                    await $.ajax({
                        url: "/assets/dyeing_finishing/js/list_layout.js?v=20261004-4",
                        dataType: "script",
                        cache: true,
                    });
                } catch (error) {
                    console.error(error);
                }
                open_settings = frappe.dyeing_finishing?.open_list_layout_settings;
            }
            if (!open_settings) {
                frappe.msgprint(__("统一列表设置加载失败，请联系管理员检查页面错误日志。"));
                return;
            }
            open_settings(listview, "Dyeing Material Item");
        };
        listview.page.set_primary_action(__("Add Item"), () => {
            frappe.new_doc("Item", {
                custom_is_dyeing_material: 1,
                item_group: "染料",
                stock_uom: "Kg",
                is_stock_item: 1,
            });
        });
    }

    settings.onload = function (listview) {
        original_onload?.call(this, listview);
        listview.page.main.parent().addClass("dyeing-item-list");
        configure_dyeing_material_list(listview);
    };

    settings.refresh = function (listview) {
        original_refresh?.call(this, listview);
        configure_dyeing_material_list(listview);
    };

    frappe.listview_settings["Item"] = settings;
})();
