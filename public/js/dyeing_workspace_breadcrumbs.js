/* eslint-disable */
(() => {
    const ROOT_WORKSPACE = "印染整理";
    const CHILD_WORKSPACES = new Set(["印染基础资料", "配方与工艺", "胚布管理", "生产管理", "染料管理", "成品管理", "系统管理"]);
    const WORKSPACE_LABELS = { "印染基础资料": "基础资料" };
    const WORKSPACE_ROUTES = { "基础资料": "印染基础资料" };
    const SHARED_ROUTE_CONTEXT_KEY = "dyeing_finishing.shared_route_owner";
    const ITEM_PROFILE_KEY = "dyeing_finishing.item_profile";
    const SHARED_ROUTES = {
        "item": ["染料管理", "染料物料档案"],
        "item group": ["基础资料", "物料组"],
        "warehouse": ["基础资料", "仓库资料"],
        "customer": ["基础资料", "客户资料"],
        "supplier": ["基础资料", "供应商资料"],
        "employee": ["基础资料", "员工资料"],
        "uom": ["基础资料", "计量单位"],
        "purchase receipt": ["染料管理", "染料采购入库单"],
        "sales order": ["生产管理", "销售订单"],
        "company": ["系统管理", "公司资料设置"],
    };
    const ROUTES = {
        "Process Requirement": ["基础资料", "加工要求"], "Packaging Requirement": ["基础资料", "包装要求"], "Production Operation": ["基础资料", "生产工序"], "Process Parameter Template": ["基础资料", "工艺参数模板"], "Grey Fabric Master": ["基础资料", "胚布档案"],
        "Dyeing System Settings": ["系统管理", "系统设置"], "Dyeing Finishing License": ["系统管理", "授权管理"], "Company Name Change": ["系统管理", "公司名称变更"], "Dyeing Paper Format": ["系统管理", "纸张规格"], "dyeing-report-engine-diagnostics": ["系统管理", "报表引擎诊断"], "dyeing-print-template-manager": ["系统管理", "报表设计中心"], "dyeing-visual-report-designer": ["系统管理", "可视化报表设计"], "crispy-format-builder": ["系统管理", "高级模板设置"], "crispy-print-preview": ["系统管理", "报表预览"],
        "Color Master": ["配方与工艺", "色号档案"], "Laboratory Recipe": ["配方与工艺", "化验室配方档案"],
        "Customer Grey Fabric Receipt": ["胚布管理", "客户胚布入库"], "Grey Fabric Issue": ["胚布管理", "胚布出库单"], "Grey Fabric Customer Transfer": ["胚布管理", "胚布过户单"], "Customer Grey Fabric Return": ["胚布管理", "客户胚布退货单"], "Grey Fabric Stock": ["胚布管理", "胚布库存"], "Production Transit Warehouse Stock": ["胚布管理", "生产中转仓库存"],
        "Dyeing Sales Order": ["生产管理", "染整销售订单"], "Production Flow Card": ["生产管理", "生产流转卡"], "Production Flow Card Rework": ["生产管理", "生产流转卡回修"], "Production Flow Card Progress Query": ["生产管理", "生产流转卡进度查询"], "Production Operation Report": ["生产管理", "生产工序报工记录"], "Employee Operation Permission": ["生产管理", "员工工序设置"], "shop-floor-reporting": ["生产管理", "生产工序扫码报工"], "Production Work Center": ["基础资料", "生产工段"], "Production Resource": ["基础资料", "生产机台"], "Production Shift": ["基础资料", "生产班次"], "Machine Production Calendar": ["生产管理", "设备停机记录"], "Dyeing Production Schedule": ["生产管理", "排程记录"], "production-schedule-board": ["生产管理", "生产排程操作台"], "production-progress-screen": ["生产管理", "生产进度大屏"], "Site Dyeing Material Sheet": ["生产管理", "现场染色料单"],
        "Site Dyeing Material Issue": ["染料管理", "现场染色领料单"], "Dye Material Stock": ["染料管理", "染料库存"], "Dye Material Other Issue": ["染料管理", "染料其他出库单"], "Dye Material Return": ["染料管理", "染料退货单"], "Dye Material Return Register": ["染料管理", "染料退货记录"],
        "Finished Product Packing Receipt": ["成品管理", "成品包装入库单"], "Finished Product Delivery": ["成品管理", "成品出库单"], "Finished Product Customer Transfer": ["成品管理", "成品转客户单"], "Finished Product Return": ["成品管理", "成品退货处理单"], "Finished Product Stock": ["成品管理", "成品库存查询"], "Finished Product Return Stock": ["成品管理", "成品退货库存查询"], "Finished Product Return to Grey Fabric": ["成品管理", "成品退货转胚布仓"], "Finished Product to Grey Fabric": ["成品管理", "成品库存转胚布仓"], "Finished Product Blank Label": ["成品管理", "成品空白标签打印单"],
    };
    const normalized = (value) => String(value || "").replace(/-/g, " ").replace(/\s+/g, " ").trim().toLowerCase();
    const workspace_route = (name) => `/desk/${frappe.router.slug(WORKSPACE_ROUTES[name] || name)}`;
    const shared_route_config = (value) => SHARED_ROUTES[normalized(value)];
    const stored_shared_route = () => window.sessionStorage.getItem(SHARED_ROUTE_CONTEXT_KEY);
    const remember_shared_route = (value) => window.sessionStorage.setItem(SHARED_ROUTE_CONTEXT_KEY, normalized(value));
    const forget_shared_route = () => window.sessionStorage.removeItem(SHARED_ROUTE_CONTEXT_KEY);

    function install_shared_route_ownership() {
        const Sidebar = frappe.ui?.Sidebar;
        if (!Sidebar || Sidebar.prototype.__dyeing_shared_route_ownership) return;

        const original_get_sidebars = Sidebar.prototype.get_workspace_sidebars;
        const original_resolve_sidebar = Sidebar.prototype.resolve_sidebar;

        Sidebar.prototype.get_workspace_sidebars = function (link_to) {
            const sidebars = original_get_sidebars.call(this, link_to);
            const target = normalized(link_to);
            const belongs_to_dyeing = shared_route_config(target)
                && (this.sidebar_title === ROOT_WORKSPACE || stored_shared_route() === target);
            if (belongs_to_dyeing && !sidebars.includes(ROOT_WORKSPACE)) sidebars.push(ROOT_WORKSPACE);
            return sidebars;
        };

        Sidebar.prototype.resolve_sidebar = function (entity, module) {
            const target = normalized(entity);
            if (shared_route_config(target)) {
                if (this.sidebar_title === ROOT_WORKSPACE) remember_shared_route(target);
                if (this.sidebar_title === ROOT_WORKSPACE || stored_shared_route() === target) {
                    this.preferred_sidebars = this.get_workspace_sidebars(entity);
                    return ROOT_WORKSPACE;
                }
            }
            return original_resolve_sidebar.call(this, entity, module);
        };

        Sidebar.prototype.__dyeing_shared_route_ownership = true;
    }
    function route_target() {
        const route = frappe.get_route() || [];
        const view = String(route[0] || "").toLowerCase();
        if (["query-report", "report"].includes(view)) return route[1];
        if (Object.keys(ROUTES).some((key) => normalized(key) === normalized(route[0]))) return route[0];
        return route[1] === "private" ? route[2] : (frappe.router.doctype_layout || route[1]);
    }
    function document_config() {
        const target = normalized(route_target());
        const shared = shared_route_config(target);
        if (shared) {
            const belongs_to_dyeing = frappe.app?.sidebar?.sidebar_title === ROOT_WORKSPACE
                || stored_shared_route() === target;
            if (!belongs_to_dyeing) return null;
            if (target === "item" && window.sessionStorage.getItem(ITEM_PROFILE_KEY) === "finished_product") {
                return ["成品管理", "成品物料档案"];
            }
            return shared;
        }
        const config = Object.entries(ROUTES).find(([key]) => normalized(key) === target)?.[1];
        if (target === normalized("Production Flow Card")) {
            const route = frappe.get_route() || [];
            const view = String(route[0] || "").toLowerCase();
            const params = new URLSearchParams(window.location.search);
            const has_rework_filter = params.getAll("flow_card_type").some((value) => {
                try {
                    const parsed = JSON.parse(value);
                    return Array.isArray(parsed) && parsed[0] !== "!=" && parsed[1] === "回修";
                } catch (error) {
                    return value === "回修";
                }
            });
            const current_form_is_rework = view === "form"
                && window.cur_frm?.doctype === "Production Flow Card"
                && window.cur_frm?.doc?.name === route[2]
                && window.cur_frm?.doc?.flow_card_type === "回修";
            const explicit_mode = params.get("mode");
            const is_rework = explicit_mode === "rework" || (explicit_mode !== "normal" && (params.get("rework") === "1" || has_rework_filter
                || current_form_is_rework));
            return is_rework ? ["生产管理", "生产流转卡回修"] : config;
        }
        return config;
    }
    function workspace_config() {
        const route = frappe.get_route() || [];
        const target = route[1] === "private" ? route[2] : route[1];
        return CHILD_WORKSPACES.has(target) ? (WORKSPACE_LABELS[target] || target) : null;
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
            const documentName = route.slice(2).join("/");
            const displayName = documentName.startsWith("new-") ? `新建${item[1]}` : documentName;
            append($breadcrumbs, "", displayName, true);
        } else {
            append($breadcrumbs, "", item[1], true);
        }
    }
    function update_shared_route_context() {
        const target = normalized(route_target());
        if (!shared_route_config(target)) forget_shared_route();
    }
    function mark_dyeing_ui_context() {
        const active = frappe.app?.sidebar?.sidebar_title === ROOT_WORKSPACE
            || Boolean(workspace_config())
            || Boolean(document_config());
        document.body.classList.toggle("dyeing-finishing-ui", active);
    }
    function schedule() {
        install_shared_route_ownership();
        install_breadcrumb_observer();
        [80, 350, 800, 1500].forEach((delay) => window.setTimeout(() => {
            mark_dyeing_ui_context();
            render();
        }, delay));
    }
    let breadcrumb_observer;
    let breadcrumb_observer_target;
    let restoring_breadcrumbs = false;
    function install_breadcrumb_observer() {
        const breadcrumbs = document.querySelector(".navbar-breadcrumbs");
        if (!breadcrumbs || breadcrumb_observer_target === breadcrumbs) return;
        if (breadcrumb_observer) breadcrumb_observer.disconnect();
        breadcrumb_observer_target = breadcrumbs;
        breadcrumb_observer = new MutationObserver(() => {
            if (restoring_breadcrumbs || !document_config()) return;
            const text = breadcrumbs.textContent || "";
            if (text.includes(ROOT_WORKSPACE) && text.includes(document_config()[0])) return;
            restoring_breadcrumbs = true;
            window.setTimeout(() => {
                render();
                restoring_breadcrumbs = false;
            }, 0);
        });
        breadcrumb_observer.observe(breadcrumbs, { childList: true, subtree: true, characterData: true });
    }
    install_shared_route_ownership();
    mark_dyeing_ui_context();
    frappe.router.on("change", schedule);
    frappe.router.on("change", update_shared_route_context);
    $(document).on("form-load list-refresh workspace-render report-refresh page-change", schedule);
    $(schedule);
})();
