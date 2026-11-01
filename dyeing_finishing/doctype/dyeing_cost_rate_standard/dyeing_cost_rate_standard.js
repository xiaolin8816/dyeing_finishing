const COST_RATE_STANDARD_METHOD = "dyeing_finishing.dyeing_finishing.doctype.dyeing_cost_rate_standard.dyeing_cost_rate_standard.";

function apply_cost_rate_standard_layout(frm) {
    ["document_section", "scope_section", "version_source_section"].forEach((fieldname) => {
        frm.get_field(fieldname)?.wrapper?.addClass("dyeing-responsive-form-grid");
    });

    const $section_head = frm.get_field("rate_items_section")?.wrapper?.find(".section-head").first();
    const $grid = frm.get_field("rate_items")?.$wrapper;
    $grid?.find(".grid-field > .control-label").first().hide();
    if (!$section_head?.length) return;

    $section_head.find(".dyeing-select-cost-elements").remove();
    if (frm.doc.docstatus === 0 && frm.get_field("rate_items")?.get_status() === "Write") {
        $section_head.css({display: "flex", alignItems: "center", flexWrap: "wrap", columnGap: "12px"});
        $("<button>", {
            type: "button",
            class: "btn btn-xs btn-secondary dyeing-select-cost-elements",
            text: "选择成本要素",
        })
            .on("click", () => select_cost_elements(frm))
            .appendTo($section_head);
    }
}

async function select_cost_elements(frm) {
    await frappe.model.with_doctype("Dyeing Cost Element");
    const existing = new Set((frm.doc.rate_items || [])
        .filter((row) => row.cost_element
            && !row.production_operation
            && !row.work_center
            && !row.production_resource)
        .map((row) => row.cost_element));

    const dialog = new frappe.ui.form.MultiSelectDialog({
        doctype: "Dyeing Cost Element",
        target: frm,
        setters: {},
        add_filters_group: false,
        size: "large",
        columns: ["要素编码", "成本要素名称", "成本类别", "默认计费方式"],
        primary_action_label: "添加所选要素",
        get_query() {
            return {
                query: COST_RATE_STANDARD_METHOD + "search_rate_cost_elements",
            };
        },
        async action(selections) {
            if (!selections.length) {
                frappe.msgprint("请至少选择一个成本要素。");
                return;
            }
            const names = selections.filter((name) => !existing.has(name));
            if (!names.length) {
                frappe.show_alert({message: "所选成本要素已在明细中", indicator: "orange"});
                dialog.dialog.hide();
                return;
            }
            const response = await frappe.call({
                method: COST_RATE_STANDARD_METHOD + "get_rate_cost_elements",
                args: {
                    company: frm.doc.company || "",
                    cost_elements: names,
                },
                freeze: true,
                freeze_message: "正在加入成本要素…",
            });
            const rows = response.message || [];
            rows.forEach((values) => Object.assign(frm.add_child("rate_items"), values));
            frm.refresh_field("rate_items");
            await frm.set_value("rate_item_count", (frm.doc.rate_items || []).length);
            dialog.dialog.hide();
            frappe.show_alert({
                message: `已加入 ${rows.length} 个成本要素`,
                indicator: "green",
            });
        },
    });
    dialog.page_length = 1000;
    dialog.dialog.set_title("选择成本要素档案");
    dialog.dialog.set_df_property("search_term", "label", "要素查询");
    dialog.dialog.set_df_property("search_term", "placeholder", "输入编码、名称或类别");
    dialog.dialog.get_secondary_btn().hide();
    dialog.get_results();
}

function make_new_rate_version(frm) {
    frappe.model.open_mapped_doc({
        method: COST_RATE_STANDARD_METHOD + "make_new_version",
        frm,
    });
}

function recalculate_rate_row(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    frappe.model.set_value(cdt, cdn, "standard_cost", flt(row.standard_consumption) * flt(row.unit_rate));
}

async function apply_cost_element_defaults(cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row.cost_element) return;
    const response = await frappe.db.get_value("Dyeing Cost Element", row.cost_element, [
        "element_name", "cost_category", "default_uom", "default_calculation_basis",
    ]);
    const values = response.message || {};
    await frappe.model.set_value(cdt, cdn, "cost_category", values.cost_category || "其他");
    await frappe.model.set_value(cdt, cdn, "cost_item", values.element_name || row.cost_element);
    await frappe.model.set_value(cdt, cdn, "uom", values.default_uom || "");
    await frappe.model.set_value(
        cdt, cdn, "calculation_basis",
        ["每公斤", "每批", "每小时", "固定金额"].includes(values.default_calculation_basis)
            ? values.default_calculation_basis : ""
    );
}

frappe.ui.form.on("Dyeing Cost Rate Standard", {
    setup(frm) {
        frm.set_df_property("rate_items", "cannot_add_rows", true);
        if (frm.is_new() && !frm.doc.company) {
            frm.set_value("company", frappe.defaults.get_user_default("Company"));
        }
        frm.set_query("cost_element", "rate_items", () => ({
            filters: {
                company: frm.doc.company || "__no_company__",
                is_active: 1,
                enable_estimate: 1,
            },
        }));
        frm.set_query("production_resource", "rate_items", (doc, cdt, cdn) => {
            const row = locals[cdt][cdn];
            const filters = {status: ["!=", "停用"]};
            if (row.work_center) filters.work_center = row.work_center;
            return {filters};
        });
    },
    onload(frm) {
        if (!frm.is_new() || (frm.doc.rate_items || []).length !== 1) return;
        const row = frm.doc.rate_items[0];
        if (row.cost_element || row.cost_item || row.uom || row.production_operation
            || row.work_center || row.production_resource || row.remarks || flt(row.unit_rate)
            || flt(row.standard_cost) || flt(row.standard_consumption) > 1
            || (row.calculation_basis && row.calculation_basis !== "每公斤")
            || (row.cost_category && row.cost_category !== "胚布")) return;
        frm.clear_table("rate_items");
        frm.refresh_field("rate_items");
        frm.set_value("rate_item_count", 0);
    },
    refresh(frm) {
        frm.set_df_property("rate_items", "cannot_add_rows", true);
        apply_cost_rate_standard_layout(frm);
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button("创建新费率版本", () => make_new_rate_version(frm), "费率操作");
        }
    },
});

frappe.ui.form.on("Dyeing Cost Rate Standard Item", {
    rate_items_add(frm) {
        frm.set_value("rate_item_count", (frm.doc.rate_items || []).length);
    },
    rate_items_remove(frm) {
        frm.set_value("rate_item_count", (frm.doc.rate_items || []).length);
    },
    cost_element(frm, cdt, cdn) {
        return apply_cost_element_defaults(cdt, cdn);
    },
    standard_consumption: recalculate_rate_row,
    unit_rate: recalculate_rate_row,
    work_center(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.production_resource) {
            frappe.model.set_value(cdt, cdn, "production_resource", "");
        }
    },
});
