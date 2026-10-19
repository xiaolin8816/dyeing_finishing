function production_flow_card_is_rework_context() {
    const params = new URLSearchParams(window.location.search);
    if (params.get("mode") === "normal") return false;
    if (params.get("mode") === "rework") return true;
    if (params.get("rework") === "1") return true;
    return params.getAll("flow_card_type").some((value) => {
        try {
            const parsed = JSON.parse(decodeURIComponent(value || ""));
            return Array.isArray(parsed) && parsed[0] !== "!=" && parsed[1] === "回修";
        } catch (error) {
            return decodeURIComponent(value || "") === "回修";
        }
    });
}

async function normalize_production_flow_card_type_filter(listview) {
    if (listview.__normalizing_flow_card_type_filter) return;
    if (!listview.filter_area?.filter_list || !listview.filter_area.get) return;
    const isRework = production_flow_card_is_rework_context();
    const desiredOperator = isRework ? "=" : "!=";
    const typeFilters = listview.filter_area.get().filter((filter) => filter[1] === "flow_card_type");
    const isCorrect = typeFilters.length === 1
        && typeFilters[0][2] === desiredOperator
        && typeFilters[0][3] === "回修";
    if (isCorrect) return;

    listview.__normalizing_flow_card_type_filter = true;
    try {
        // flow_card_type can be either a standard filter control ("=") or a
        // filter-list row ("!="). Remove through FilterArea so both storage
        // locations are cleared. Removing only filter_list rows leaves a stale
        // "= 回修" value behind when switching from rework to normal.
        listview.filter_area.trigger_refresh = false;
        for (let attempt = 0; attempt < 5; attempt += 1) {
            const remaining = listview.filter_area.get()
                .filter((filter) => filter[1] === "flow_card_type");
            if (!remaining.length) break;
            await listview.filter_area.remove("flow_card_type");
        }
        listview.filter_area.trigger_refresh = true;
        await listview.filter_area.add([
            ["Production Flow Card", "flow_card_type", desiredOperator, "回修"],
        ]);
    } finally {
        listview.filter_area.trigger_refresh = true;
        listview.__normalizing_flow_card_type_filter = false;
    }
}

function configure_production_flow_card_list(listview) {
    const isRework = production_flow_card_is_rework_context();
    const title = isRework ? "生产流转卡回修" : "生产流转卡";
    const buttonLabel = isRework ? "新建生产流转卡回修" : "新建生产流转卡";
    listview.page.set_title(__(title));
    listview.page.set_primary_action(__(buttonLabel), () => {
        frappe.route_options = {
            flow_card_type: isRework ? "回修" : "正常生产",
        };
        frappe.new_doc("Production Flow Card");
    }, "add");
}

frappe.listview_settings["Production Flow Card"] = {
    onload(listview) {
        // route_options can survive a previous list/new-document transition.
        // The URL is the single source of truth for normal versus rework lists.
        frappe.route_options = null;
        configure_production_flow_card_list(listview);
        normalize_production_flow_card_type_filter(listview);
    },
    refresh(listview) {
        configure_production_flow_card_list(listview);
        normalize_production_flow_card_type_filter(listview);
    },
};
