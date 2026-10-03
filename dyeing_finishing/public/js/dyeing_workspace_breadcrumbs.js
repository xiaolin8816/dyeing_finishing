/* eslint-disable */
(() => {
    const ROOT_WORKSPACE = "印染整理";
    const CHILD_WORKSPACES = new Set(["印染基础资料", "配方与工艺", "胚布管理", "生产管理", "染料管理"]);
    const ROUTES = {
        "Process Requirement": ["印染基础资料", "加工要求"], "Packaging Requirement": ["印染基础资料", "包装要求"], "Production Operation": ["印染基础资料", "生产工序"], "Process Parameter Template": ["印染基础资料", "工艺参数模板"], "Dyeing Machine": ["印染基础资料", "染色机台"], "Grey Fabric Master": ["印染基础资料", "胚布档案"],
        "Color Master": ["配方与工艺", "色号档案"], "Laboratory Recipe": ["配方与工艺", "化验室配方档案"],
        "Customer Grey Fabric Receipt": ["胚布管理", "客户胚布入库"], "Grey Fabric Issue": ["胚布管理", "胚布出库单"], "Grey Fabric Stock": ["胚布管理", "胚布库存"], "Production Transit Warehouse Stock": ["胚布管理", "生产中转仓库存"],
        "Production Flow Card": ["生产管理", "生产流转卡"], "Site Dyeing Material Sheet": ["生产管理", "现场染色料单"],
        "Site Dyeing Material Issue": ["染料管理", "现场染色领料单"], "Dye Material Receipt Register": ["染料管理", "染料入库记录"], "Dye Material Stock": ["染料管理", "染料库存"], "Dye Material Other Issue": ["染料管理", "染料其他出库单"], "Dye Material Return": ["染料管理", "染料退货单"],
    };
    const normalized = (value) => String(value || "").replace(/-/g, " ").replace(/\s+/g, " ").trim().toLowerCase();
    const workspace_route = (name) => `/desk/${frappe.router.slug(name)}`;
    function route_target() {
        const route = frappe.get_route() || [];
        return route[1] === "private" ? route[2] : (frappe.router.doctype_layout || route[1]);
    }
    function document_config() {
        const target = normalized(route_target());
        return Object.entries(ROUTES).find(([key]) => normalized(key) === target)?.[1];
    }
    function workspace_config() {
        const route = frappe.get_route() || [];
        const target = route[1] === "private" ? route[2] : route[1];
        return CHILD_WORKSPACES.has(target) ? target : null;
    }
    function append($breadcrumbs, href, label, disabled = false, raw = false) {
        const text = raw ? label : frappe.utils.escape_html(label);
        const item = $("<li><a href=\"" + (href || "") + "\">" + text + "</a></li>");
        if (disabled) item.addClass("disabled");
        $breadcrumbs.append(item);
    }
    function render() {
        const workspace = workspace_config();
        const item = document_config();
        if (!workspace && !item) return;
        const route = frappe.get_route() || [];
        const view = String(route[0] || "").toLowerCase();
        const $breadcrumbs = $(".navbar-breadcrumbs");
        if (!$breadcrumbs.length) return;
        $breadcrumbs.empty();
        append($breadcrumbs, "/desk", frappe.utils.icon("home"), false, true);
        append($breadcrumbs, workspace_route(ROOT_WORKSPACE), ROOT_WORKSPACE);
        if (workspace) {
            append($breadcrumbs, "", workspace, true);
            return;
        }
        append($breadcrumbs, workspace_route(item[0]), item[0]);
        if (view === "form") {
            append($breadcrumbs, `/desk/${frappe.router.slug(route_target())}`, item[1]);
            append($breadcrumbs, "", route.slice(2).join("/"), true);
        } else {
            append($breadcrumbs, "", item[1], true);
        }
    }
    function schedule() { window.setTimeout(render, 80); window.setTimeout(render, 350); }
    frappe.router.on("change", schedule);
    $(document).on("form-load list-refresh workspace-render", schedule);
})();