(() => {
    const ROOT_WORKSPACE = "印染整理";
    const PROFILE_KEY = "dyeing_finishing.item_profile";
    const settings = frappe.boot.dyeing_system_settings || {};
    const FINISHED_ITEM_GROUP = settings.finished_product_item_group || "成品";
    const ALLOWED_DYEING_ITEM_GROUPS = [settings.dye_item_group || "染料", settings.auxiliary_item_group || "助剂"];
    const WEIGHT_UOM = settings.weight_uom || "Kg";
    const active_profile = () => window.sessionStorage.getItem(PROFILE_KEY) || "";
    const entered_from_dyeing = () => frappe.app?.sidebar?.sidebar_title === ROOT_WORKSPACE;

    function is_dyeing_material_entry(frm) {
        return Boolean(frm.doc.custom_is_dyeing_material)
            || (frm.is_new() && entered_from_dyeing() && active_profile() === "dyeing_material");
    }

    function is_finished_product_entry(frm) {
        return Boolean(frm.doc.custom_is_finished_product)
            || (frm.is_new() && entered_from_dyeing() && active_profile() === "finished_product");
    }

    function apply_item_group_filter(frm) {
        if (is_finished_product_entry(frm)) {
            frm.set_query("item_group", () => ({filters: {name: FINISHED_ITEM_GROUP, is_group: 0}}));
        } else if (is_dyeing_material_entry(frm)) {
            frm.set_query("item_group", () => ({
                filters: {name: ["in", ALLOWED_DYEING_ITEM_GROUPS], is_group: 0},
            }));
        }
    }

    function apply_finished_product_labels(frm) {
        if (!is_finished_product_entry(frm)) return;
        frm.set_df_property("item_code", "label", "成品编码");
        frm.set_df_property("item_code", "read_only", 1);
        frm.set_df_property("item_code", "reqd", 0);
        frm.set_df_property("item_name", "label", "成品名称");
    }

    function update_finished_specification(frm) {
        if (!is_finished_product_entry(frm)) return;
        const width = String(frm.doc.custom_finished_width || "").trim();
        const gsm = String(frm.doc.custom_finished_gsm || "").trim();
        const gsm_value = gsm ? `${gsm}${frm.doc.custom_finished_gsm_uom || "g/㎡"}` : "";
        frm.set_value("custom_finished_specification", [width, gsm_value].filter(Boolean).join(" × "));
    }

    frappe.ui.form.on("Item", {
        setup(frm) {
            apply_item_group_filter(frm);
            frm.set_query("custom_finished_color_no", () => ({filters: {status: "启用"}}));
        },

        async onload(frm) {
            apply_item_group_filter(frm);
            apply_finished_product_labels(frm);
            if (frm.is_new() && is_finished_product_entry(frm)) {
                await frm.set_value({
                    custom_is_finished_product: 1,
                    custom_is_dyeing_material: 0,
                    item_group: FINISHED_ITEM_GROUP,
                    stock_uom: WEIGHT_UOM,
                    is_stock_item: 1,
                    has_batch_no: 1,
                    custom_finished_gsm_uom: frm.doc.custom_finished_gsm_uom || "g/㎡",
                });
            } else if (frm.is_new() && is_dyeing_material_entry(frm)) {
                await frm.set_value({
                    custom_is_dyeing_material: 1,
                    custom_is_finished_product: 0,
                    item_group: frm.doc.item_group || ALLOWED_DYEING_ITEM_GROUPS[0],
                    stock_uom: frm.doc.stock_uom || WEIGHT_UOM,
                    is_stock_item: 1,
                });
            }
        },

        refresh(frm) {
            apply_item_group_filter(frm);
            apply_finished_product_labels(frm);
        },

        custom_finished_color_no(frm) {
            if (!frm.doc.custom_finished_color_no || !is_finished_product_entry(frm)) return;
            frappe.db.get_doc("Color Master", frm.doc.custom_finished_color_no).then((color) => {
                frm.set_value("custom_finished_color", color.color_name || "");
                frm.set_value("custom_finished_customer", color.customer_name || "");
                if (!frm.doc.item_name) frm.set_value("item_name", color.product_name || "");
            });
        },

        custom_finished_width: update_finished_specification,
        custom_finished_gsm: update_finished_specification,
        custom_finished_gsm_uom: update_finished_specification,

        validate(frm) {
            if (frm.doc.custom_is_finished_product && frm.doc.item_group !== FINISHED_ITEM_GROUP) {
                frappe.throw(__("成品物料的物料组只能选择成品。"));
            }
            if (frm.doc.custom_is_dyeing_material && !ALLOWED_DYEING_ITEM_GROUPS.includes(frm.doc.item_group)) {
                frappe.throw(__("染化料物料的物料组只能选择染料或助剂。"));
            }
        },
    });
})();
