/* eslint-disable */
(() => {
    const PREVIEW_ROUTE = "crispy-print-preview";
    const BUTTON_CLASS = "dyeing-preview-close";
    const FIXED_TEMPLATE_CLASS = "dyeing-fixed-template-preview";
    const STYLE_ID = "dyeing-crispy-preview-style";

    function install_preview_style() {
        if (document.getElementById(STYLE_ID)) return;
        $("<style>", { id: STYLE_ID, text: `
            body.${FIXED_TEMPLATE_CLASS} .settings-pane__template-section {
                display: none !important;
            }
        ` }).appendTo(document.head);
    }

    function sync_fixed_template_mode() {
        const route = frappe.get_route() || [];
        // The fourth route segment identifies an explicitly selected format.
        // It is already fixed for this preview, so the large selector card is redundant.
        const is_fixed_preview = route[0] === PREVIEW_ROUTE && Boolean(route[3]);
        document.body.classList.toggle(FIXED_TEMPLATE_CLASS, is_fixed_preview);
    }

    function close_preview() {
        const route = frappe.get_route() || [];
        const doctype = route[1];
        const docname = route[2];

        if (window.opener && !window.opener.closed) {
            window.close();
            // Some browser policies may reject window.close(). In that case,
            // continue with an in-app route instead of leaving a dead preview.
            window.setTimeout(() => {
                if (!window.closed) return_to_source(doctype, docname);
            }, 150);
            return;
        }
        return_to_source(doctype, docname);
    }

    function return_to_source(doctype, docname) {
        if (doctype && docname && doctype !== "report") {
            frappe.set_route("Form", doctype, docname);
            return;
        }
        frappe.set_route("dyeing-print-template-manager");
    }

    function install_close_button() {
        const route = frappe.get_route() || [];
        if (route[0] !== PREVIEW_ROUTE) return;

        const page = frappe.pages?.[PREVIEW_ROUTE]?.print_view?.page;
        if (!page || page.wrapper.find(`.${BUTTON_CLASS}`).length) return;

        const button = page.add_button(__("Close"), close_preview, {
            icon: "close-alt",
        });
        button?.addClass(BUTTON_CLASS);
        button?.attr("title", __("关闭预览并返回来源单据"));
    }

    function schedule_install() {
        install_preview_style();
        sync_fixed_template_mode();
        [0, 100, 350, 800].forEach((delay) => window.setTimeout(install_close_button, delay));
    }

    $(document).on("page-change", schedule_install);
    frappe.router?.on?.("change", schedule_install);
    $(schedule_install);
})();
