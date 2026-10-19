/* eslint-disable */
(() => {
    const API = "dyeing_finishing.api.get_document_print_templates";
    const BLANK_LABEL_API =
        "dyeing_finishing.dyeing_finishing.doctype.finished_product_blank_label.finished_product_blank_label.record_blank_label_print";
    const ACTION_LABEL = "报表打印";
    const MAX_BATCH = 20;

    async function getTemplates(doctype, docname) {
        const response = await frappe.call({
            method: API,
            args: { doctype, docname: docname || "" },
        });
        return response.message || [];
    }

    function previewUrl(doctype, docname, template) {
        return `/desk/crispy-print-preview/${encodeURIComponent(doctype)}/${encodeURIComponent(docname)}/${encodeURIComponent(template)}`;
    }

    function chooseTemplate(templates) {
        if (templates.length === 1) return Promise.resolve(templates[0]);
        return new Promise((resolve) => {
            let completed = false;
            const dialog = new frappe.ui.Dialog({
                title: "选择报表模板",
                fields: [{
                    fieldname: "template",
                    fieldtype: "Select",
                    label: "打印模板",
                    reqd: 1,
                    options: templates.map((row) => ({
                        label: `${row.name}${row.is_default ? "（默认）" : ""} · ${row.paper}`,
                        value: row.name,
                    })),
                    default: (templates.find((row) => row.is_default) || templates[0]).name,
                }],
                primary_action_label: "确定",
                primary_action(values) {
                    completed = true;
                    dialog.hide();
                    resolve(templates.find((row) => row.name === values.template));
                },
            });
            dialog.$wrapper.on("hidden.bs.modal", () => {
                if (!completed) resolve(null);
            });
            dialog.show();
        });
    }

    function askQuantity(defaultValue = 1) {
        return new Promise((resolve) => {
            let completed = false;
            const dialog = new frappe.ui.Dialog({
                title: "打印空白标签",
                fields: [{
                    fieldname: "print_quantity",
                    fieldtype: "Int",
                    label: "本次打印数量",
                    reqd: 1,
                    default: defaultValue || 1,
                    description: "仅表示本次标签张数，不作为包装匹数或库存数量。",
                }],
                primary_action_label: "打印",
                primary_action(values) {
                    const quantity = cint(values.print_quantity);
                    if (quantity < 1 || quantity > 1000) {
                        frappe.msgprint(__("本次打印数量应在 1 至 1000 张之间。"));
                        return;
                    }
                    completed = true;
                    dialog.hide();
                    resolve(quantity);
                },
            });
            dialog.$wrapper.on("hidden.bs.modal", () => {
                if (!completed) resolve(null);
            });
            dialog.show();
        });
    }

    async function printDocuments(doctype, names, templates, defaultQuantity) {
        const template = await chooseTemplate(templates);
        if (!template) return;
        if (template.requires_quantity && names.length !== 1) {
            frappe.msgprint(__("标签打印每次只能选择一张打印单，份数在打印窗口中填写。"));
            return;
        }
        if (names.length > MAX_BATCH) {
            frappe.msgprint(__("一次最多打印 {0} 张单据。", [MAX_BATCH]));
            return;
        }

        let quantity = null;
        if (template.requires_quantity) {
            quantity = await askQuantity(defaultQuantity);
            if (!quantity) return;
        }

        const windows = names.map(() => window.open("", "_blank"));
        try {
            if (template.requires_quantity) {
                await frappe.call({
                    method: BLANK_LABEL_API,
                    args: { name: names[0], print_quantity: quantity },
                    freeze: true,
                    freeze_message: "正在生成空白标签…",
                });
            }
            names.forEach((name, index) => {
                const url = previewUrl(doctype, name, template.name);
                if (windows[index]) windows[index].location = url;
                else window.open(url, "_blank");
            });
        } catch (error) {
            windows.forEach((printWindow) => printWindow?.close());
            throw error;
        }
    }

    async function attachFormAction(frm) {
        if (!frm || frm.is_new() || !frm.doc?.name || frm.doc.__islocal) return;
        const key = `${frm.doctype}:${frm.doc.name}`;
        if (frm.__dyeingPrintLookupKey === key) return;
        frm.__dyeingPrintLookupKey = key;
        let templates = [];
        try {
            templates = await getTemplates(frm.doctype, frm.doc.name);
        } catch (error) {
            frm.__dyeingPrintLookupKey = null;
            return;
        }
        if (!templates.length || window.cur_frm !== frm) return;
        frm.__dyeingPrintTemplates = templates;
        frm.page.add_action_item(__(ACTION_LABEL), async () => {
            await printDocuments(frm.doctype, [frm.doc.name], frm.__dyeingPrintTemplates, frm.doc.print_quantity || 1);
            if (frm.doctype === "Finished Product Blank Label") frm.reload_doc();
        });
    }

    async function attachListAction(listview) {
        if (!listview?.doctype || listview.__dyeingPrintActionAdded) return;
        listview.__dyeingPrintActionAdded = true;
        let templates = [];
        try {
            templates = await getTemplates(listview.doctype);
        } catch (error) {
            listview.__dyeingPrintActionAdded = false;
            return;
        }
        if (!templates.length) {
            listview.__dyeingPrintActionAdded = false;
            return;
        }
        const handler = async () => {
            const selected = listview.get_checked_items();
            if (!selected.length) {
                frappe.msgprint(__("请先勾选要打印的单据。"));
                return;
            }
            const documentTemplates = await getTemplates(listview.doctype, selected[0].name);
            if (!documentTemplates.length) {
                frappe.msgprint(__("所选单据没有可用的已发布报表模板。"));
                return;
            }
            await printDocuments(listview.doctype, selected.map((row) => row.name), documentTemplates, selected[0].print_quantity || 1);
            listview.refresh();
        };
        listview.page.add_actions_menu_item(__(ACTION_LABEL), handler);
        const button = listview.page.add_inner_button(__(ACTION_LABEL), handler);
        button?.addClass?.("btn-primary");
    }

    function installHooks() {
        const formPrototype = frappe.ui?.form?.Form?.prototype;
        if (formPrototype && !formPrototype.__dyeingPrintHook) {
            formPrototype.__dyeingPrintHook = true;
            const originalRefresh = formPrototype.refresh;
            formPrototype.refresh = function (...args) {
                // Form.refresh rebuilds the Actions menu, so its print entry
                // must be attached again even when the document did not change.
                this.__dyeingPrintLookupKey = null;
                const result = originalRefresh.apply(this, args);
                Promise.resolve(result).finally(() => window.setTimeout(() => attachFormAction(this), 0));
                return result;
            };
        }

        const listPrototype = frappe.views?.ListView?.prototype;
        if (listPrototype && !listPrototype.__dyeingPrintHook) {
            listPrototype.__dyeingPrintHook = true;
            const originalRefresh = listPrototype.refresh;
            listPrototype.refresh = function (...args) {
                this.__dyeingPrintActionAdded = false;
                const result = originalRefresh.apply(this, args);
                Promise.resolve(result).finally(() => window.setTimeout(() => attachListAction(this), 0));
                return result;
            };
        }
    }

    function syncCurrentView() {
        installHooks();
        if (window.cur_frm) attachFormAction(window.cur_frm);
        if (window.cur_list) attachListAction(window.cur_list);
    }

    window.dyeing_report_print = { getTemplates, printDocuments };
    $(syncCurrentView);
    function scheduleSync() {
        [0, 100, 400, 1000, 2000].forEach((delay) => window.setTimeout(syncCurrentView, delay));
    }
    $(document).on("page-change", scheduleSync);
    frappe.router?.on?.("change", scheduleSync);
})();
