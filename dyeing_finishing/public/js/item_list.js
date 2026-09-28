(() => {
    const settings = frappe.listview_settings["Item"] || {};
    const original_onload = settings.onload;

    settings.onload = function (listview) {
        original_onload?.call(this, listview);
        listview.page.main.parent().addClass("dyeing-item-list");
    };

    frappe.listview_settings["Item"] = settings;
})();
