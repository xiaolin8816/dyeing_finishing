const COST_ESTIMATE_METHOD = "dyeing_finishing.dyeing_finishing.doctype.dyeing_cost_estimate.dyeing_cost_estimate.";

const COST_BUCKETS = {
    "胚布": "grey_fabric_cost",
    "染料": "chemical_cost",
    "助剂": "chemical_cost",
    "水": "energy_cost",
    "电": "energy_cost",
    "蒸汽": "energy_cost",
    "天然气": "energy_cost",
    "污水处理": "energy_cost",
    "人工": "labor_cost",
    "机台": "machine_cost",
    "包装": "packaging_cost",
    "委外": "subcontract_cost",
    "其他": "other_cost",
};

const DEFAULT_COST_ELEMENTS = {
    "水": "CE-WATER",
    "电": "CE-ELECTRICITY",
    "蒸汽": "CE-STEAM",
    "天然气": "CE-NATURAL-GAS",
    "污水处理": "CE-WASTEWATER",
    "人工": "CE-LABOR",
    "机台": "CE-MACHINE",
    "包装": "CE-PACKAGING",
    "委外": "CE-SUBCONTRACT",
    "其他": "CE-OTHER",
};

function apply_cost_estimate_layout(frm) {
    [
        "document_section", "order_section", "order_row_2", "order_row_3",
        "cost_basis_section", "cost_basis_row_2", "cost_basis_row_3", "summary_section",
        "summary_row_2", "summary_row_3", "summary_row_4",
    ].forEach((fieldname) => frm.get_field(fieldname)?.wrapper?.addClass("dyeing-responsive-form-grid"));
}

function recalculate_cost_estimate(frm) {
    const totals = {
        grey_fabric_cost: 0, chemical_cost: 0, energy_cost: 0, labor_cost: 0,
        machine_cost: 0, packaging_cost: 0, subcontract_cost: 0, other_cost: 0,
    };
    (frm.doc.cost_items || []).forEach((row) => {
        if (frm.doc.order_type === "来料加工" && row.cost_category === "胚布") {
            row.unit_rate = 0;
        }
        row.amount = flt(row.quantity) * flt(row.unit_rate);
        totals[COST_BUCKETS[row.cost_category] || "other_cost"] += flt(row.amount);
    });
    Object.entries(totals).forEach(([fieldname, value]) => { frm.doc[fieldname] = value; });
    frm.doc.total_cost = Object.values(totals).reduce((sum, value) => sum + value, 0);
    frm.doc.unit_cost = flt(frm.doc.estimate_qty) ? frm.doc.total_cost / flt(frm.doc.estimate_qty) : 0;
    frm.doc.estimated_output_qty = flt(frm.doc.estimate_qty) * flt(frm.doc.expected_yield_rate) / 100;
    frm.doc.expected_revenue = flt(frm.doc.estimate_qty) * flt(frm.doc.order_rate);
    frm.doc.order_amount = frm.doc.expected_revenue;
    frm.doc.gross_profit = frm.doc.expected_revenue - frm.doc.total_cost;
    frm.doc.gross_margin_rate = frm.doc.expected_revenue ? frm.doc.gross_profit / frm.doc.expected_revenue * 100 : 0;
    const target = flt(frm.doc.target_gross_margin_rate);
    frm.doc.suggested_quote_rate = target >= 0 && target < 100 ? frm.doc.unit_cost / (1 - target / 100) : 0;
    frm.refresh_fields([
        "cost_items", ...Object.keys(totals), "total_cost", "unit_cost", "estimated_output_qty",
        "expected_revenue", "order_amount", "gross_profit", "gross_margin_rate", "suggested_quote_rate",
    ]);
}

async function load_estimate_source(frm, replaceItems = true) {
    if (!frm.doc.sales_order || !frm.doc.sales_order_item || frm.__loading_cost_source) return;
    frm.__loading_cost_source = true;
    try {
        const response = await frappe.call({
            method: COST_ESTIMATE_METHOD + "get_estimate_source",
            args: {
                sales_order: frm.doc.sales_order,
                sales_order_item: frm.doc.sales_order_item,
                laboratory_recipe: frm.doc.laboratory_recipe || "",
                cost_rate_standard: frm.doc.cost_rate_standard || "",
                estimate_date: frm.doc.estimate_date,
                production_resource: frm.doc.production_resource || "",
                estimated_production_hours: frm.doc.estimated_production_hours || 0,
            },
            freeze: true,
            freeze_message: "正在读取订单、配方、库存估值和成本费率…",
        });
        const data = response.message || {};
        await frm.set_value(data.values || {});
        if (replaceItems) {
            frm.clear_table("cost_items");
            (data.cost_items || []).forEach((values) => Object.assign(frm.add_child("cost_items"), values));
            frm.refresh_field("cost_items");
        }
        recalculate_cost_estimate(frm);
    } finally {
        frm.__loading_cost_source = false;
    }
}

async function choose_order_item(frm) {
    if (!frm.doc.sales_order) return;
    const response = await frappe.call({
        method: COST_ESTIMATE_METHOD + "get_order_items_for_estimate",
        args: {sales_order: frm.doc.sales_order},
    });
    const rows = response.message || [];
    if (!rows.length) {
        frappe.msgprint("该染整销售订单没有可用于测算的明细。");
        return;
    }
    if (rows.length === 1) {
        await frm.set_value("sales_order_item", rows[0].name);
        return;
    }
    const labels = new Map(rows.map((row) => [
        `${row.name} | ${row.item_name || ""} | ${row.color || ""} | ${row.qty || 0} ${row.uom || ""}`,
        row.name,
    ]));
    const dialog = new frappe.ui.Dialog({
        title: "选择订单明细",
        fields: [{
            fieldname: "order_item",
            label: "订单明细",
            fieldtype: "Select",
            options: [...labels.keys()].join("\n"),
            reqd: 1,
        }],
        primary_action_label: "确定",
        primary_action: async (values) => {
            await frm.set_value("sales_order_item", labels.get(values.order_item));
            dialog.hide();
        },
    });
    dialog.show();
}

function add_common_cost_items(frm) {
    const defaults = ["水", "电", "蒸汽", "天然气", "污水处理", "人工", "机台", "包装", "委外", "其他"];
    const existing = new Set((frm.doc.cost_items || []).map((row) => row.cost_category));
    defaults.filter((category) => !existing.has(category)).forEach((category) => {
        const row = frm.add_child("cost_items");
        Object.assign(row, {
            cost_element: DEFAULT_COST_ELEMENTS[category],
            cost_category: category,
            description: category + "预计成本",
            calculation_basis: "手工录入",
            quantity: 0,
            unit_rate: 0,
            source_type: "手工录入",
        });
    });
    frm.refresh_field("cost_items");
}

frappe.ui.form.on("Dyeing Cost Estimate", {
    setup(frm) {
        frm.set_query("sales_order", () => ({filters: {docstatus: ["<", 2]}}));
        frm.set_query("sales_order_item", () => ({
            query: COST_ESTIMATE_METHOD + "get_sales_order_items",
            filters: {sales_order: frm.doc.sales_order || ""},
        }));
        frm.set_query("laboratory_recipe", () => ({
            filters: {color_no: frm.doc.color_no || "__no_color__", recipe_status: "已确认"},
        }));
        frm.set_query("cost_rate_standard", () => ({
            filters: {company: frm.doc.company || "__no_company__", docstatus: 1},
        }));
        frm.set_query("cost_element", "cost_items", () => ({
            filters: {
                company: frm.doc.company || "__no_company__",
                is_active: 1,
                enable_estimate: 1,
            },
        }));
        frm.set_query("production_resource", () => ({filters: {status: ["!=", "停用"]}}));
    },
    async onload_post_render(frm) {
        if (frm.is_new() && frm.doc.sales_order && !frm.doc.sales_order_item && !frm.__cost_order_initialized) {
            frm.__cost_order_initialized = true;
            await choose_order_item(frm);
        }
    },
    refresh(frm) {
        apply_cost_estimate_layout(frm);
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button("从订单和配方重新读取", () => {
                frappe.confirm("重新读取会替换当前成本明细，是否继续？", () => load_estimate_source(frm, true));
            }, "测算操作");
            frm.add_custom_button("补充常用成本项", () => add_common_cost_items(frm), "测算操作");
        }
    },
    async sales_order(frm) {
        await frm.set_value("sales_order_item", "");
        frm.clear_table("cost_items");
        frm.refresh_field("cost_items");
        if (frm.doc.sales_order) await choose_order_item(frm);
    },
    async sales_order_item(frm) {
        if (frm.doc.sales_order_item) await load_estimate_source(frm, true);
    },
    async laboratory_recipe(frm) {
        if (!frm.__loading_cost_source && frm.doc.sales_order_item) await load_estimate_source(frm, true);
    },
    async cost_rate_standard(frm) {
        if (!frm.__loading_cost_source && frm.doc.sales_order_item) await load_estimate_source(frm, true);
    },
    async production_resource(frm) {
        if (!frm.__loading_cost_source && frm.doc.sales_order_item) await load_estimate_source(frm, true);
    },
    async estimated_production_hours(frm) {
        if (!frm.__loading_cost_source && frm.doc.sales_order_item) await load_estimate_source(frm, true);
    },
    async estimate_date(frm) {
        if (!frm.__loading_cost_source && frm.doc.sales_order_item) await load_estimate_source(frm, true);
    },
    estimate_qty: recalculate_cost_estimate,
    expected_yield_rate: recalculate_cost_estimate,
    target_gross_margin_rate: recalculate_cost_estimate,
});

frappe.ui.form.on("Dyeing Cost Estimate Item", {
    async cost_element(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.cost_element) return;
        const response = await frappe.db.get_value("Dyeing Cost Element", row.cost_element, [
            "element_name", "cost_category", "default_uom", "default_calculation_basis",
        ]);
        const values = response.message || {};
        await frappe.model.set_value(cdt, cdn, "cost_category", values.cost_category || "其他");
        await frappe.model.set_value(cdt, cdn, "description", values.element_name || row.cost_element);
        await frappe.model.set_value(cdt, cdn, "uom", values.default_uom || "");
        if (["每公斤", "每批", "每小时", "固定金额"].includes(values.default_calculation_basis)) {
            await frappe.model.set_value(cdt, cdn, "calculation_basis", values.default_calculation_basis);
        }
        recalculate_cost_estimate(frm);
    },
    cost_category: recalculate_cost_estimate,
    quantity: recalculate_cost_estimate,
    unit_rate: recalculate_cost_estimate,
    cost_items_remove: recalculate_cost_estimate,
});
