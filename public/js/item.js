(() => {
    const CONTEXT_KEY = "dyeing_finishing.shared_route_owner";
    const ROOT_WORKSPACE = "印染整理";
    const ALLOWED_ITEM_GROUPS = ["染料", "助剂"];

    function is_dyeing_material_entry(frm) {
        return frm.is_new()
            && (
                frm.doc.custom_is_dyeing_material
                || (
                    window.sessionStorage.getItem(CONTEXT_KEY) === "item"
                    && frappe.app?.sidebar?.sidebar_title === ROOT_WORKSPACE
                )
            );
    }

    function apply_item_group_filter(frm) {
        frm.set_query("item_group", () => ({
            filters: {
                name: ["in", ALLOWED_ITEM_GROUPS],
                is_group: 0,
            },
        }));
    }

    frappe.ui.form.on("Item", {
        setup(frm) {
            if (is_dyeing_material_entry(frm)) apply_item_group_filter(frm);
        },

        async onload(frm) {
            if (!is_dyeing_material_entry(frm)) return;

            apply_item_group_filter(frm);
            await frm.set_value({
                custom_is_dyeing_material: 1,
                item_group: frm.doc.item_group || "染料",
                stock_uom: frm.doc.stock_uom || "Kg",
                is_stock_item: 1,
            });
        },

        refresh(frm) {
            if (frm.doc.custom_is_dyeing_material || is_dyeing_material_entry(frm)) {
                apply_item_group_filter(frm);
            }
        },

        validate(frm) {
            if (
                frm.doc.custom_is_dyeing_material
                && !ALLOWED_ITEM_GROUPS.includes(frm.doc.item_group)
            ) {
                frappe.throw(__("染化料物料的物料组只能选择染料或助剂。"));
            }
        },
    });
})();
