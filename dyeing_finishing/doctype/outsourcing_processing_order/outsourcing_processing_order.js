const flow_card_method = "dyeing_finishing.dyeing_finishing.doctype.outsourcing_processing_order.outsourcing_processing_order.get_flow_card_details";

function calculate_outsourcing_totals(frm) {
    const rows = frm.doc.items || [];
    const roll_count = rows.reduce((total, row) => total + cint(row.planned_roll_count), 0);
    const weight = rows.reduce((total, row) => total + flt(row.planned_weight), 0);
    const yard_qty = rows.reduce((total, row) => total + flt(row.planned_yard_qty), 0);
    let billing_qty = flt(frm.doc.billing_qty);
    if (frm.doc.pricing_basis === "按公斤") billing_qty = weight;
    if (frm.doc.pricing_basis === "按匹") billing_qty = roll_count;
    if (frm.doc.pricing_basis === "按码") billing_qty = yard_qty;
    if (frm.doc.pricing_basis === "按批" && !billing_qty) billing_qty = 1;
    frm.set_value({
        planned_roll_count: roll_count,
        planned_weight: weight,
        planned_yard_qty: yard_qty,
        billing_qty,
        estimated_processing_fee: billing_qty * flt(frm.doc.unit_rate),
    });
}

function set_operation_details(frm) {
    const operation = (frm._outsourcing_operations || []).find(
        (row) => row.name === frm.doc.production_operation
    );
    frm.set_value({
        operation_name: operation?.operation_name || "",
        operation_sequence: operation?.sequence_no || 0,
    });
}

async function load_flow_card(frm) {
    if (!frm.doc.production_flow_card) {
        frm._outsourcing_operations = [];
        return;
    }
    const selected = frm.doc.production_flow_card;
    const response = await frappe.call({ method: flow_card_method, args: { flow_card: selected } });
    if (frm.doc.production_flow_card !== selected) return;
    const data = response.message || {};
    frm._outsourcing_operations = data.operations || [];
    await frm.set_value({
        sales_order: data.sales_order,
        customer: data.customer,
        customer_name: data.customer_name,
        customer_order_no: data.customer_order_no,
        finished_product_name: data.finished_product_name,
        color: data.color,
        order_type: data.order_type,
        company: data.company,
        source_warehouse: data.source_warehouse,
        production_operation: "",
        operation_name: "",
        operation_sequence: 0,
    });
    frm.clear_table("items");
    (data.items || []).forEach((item) => Object.assign(frm.add_child("items"), item));
    frm.refresh_field("items");
    const preferred = frm._outsourcing_operations.filter((row) => row.scheduling_mode === "委外加工");
    if (preferred.length === 1) await frm.set_value("production_operation", preferred[0].name);
    calculate_outsourcing_totals(frm);
}

frappe.ui.form.on("Outsourcing Processing Order", {
    setup(frm) {
        frm.set_query("production_flow_card", () => ({ filters: { production_status: "进行中" } }));
        frm.set_query("processing_contractor", () => {
            const filters = { status: "启用" };
            if (frm.doc.company) filters.company = frm.doc.company;
            return { filters };
        });
        frm.set_query("production_operation", () => ({
            filters: { name: ["in", (frm._outsourcing_operations || []).map((row) => row.name)], disabled: 0 },
        }));
        ["source_warehouse", "return_warehouse"].forEach((fieldname) => {
            frm.set_query(fieldname, () => ({ filters: { is_group: 0, company: frm.doc.company || "" } }));
        });
        frm.set_query("service_item", () => ({ filters: { disabled: 0, is_stock_item: 0 } }));
    },
    refresh(frm) {
        if (frm.doc.production_flow_card && !frm._outsourcing_operations) {
            frappe.call({ method: flow_card_method, args: { flow_card: frm.doc.production_flow_card } })
                .then((response) => { frm._outsourcing_operations = response.message?.operations || []; });
        }
        if (frm.doc.purchase_order) {
            frm.add_custom_button(__("查看采购订单"), () => {
                frappe.set_route("Form", "Purchase Order", frm.doc.purchase_order);
            }, __("关联凭证"));
        }
    },
    production_flow_card: load_flow_card,
    async processing_contractor(frm) {
        if (!frm.doc.processing_contractor) return;
        const values = await frappe.db.get_value(
            "Processing Contractor",
            frm.doc.processing_contractor,
            ["default_pricing_basis", "allowed_loss_rate", "default_unit_rate", "service_item", "currency"]
        );
        const contractor = values.message || {};
        await frm.set_value({
            pricing_basis: contractor.default_pricing_basis || frm.doc.pricing_basis,
            allowed_loss_rate: flt(contractor.allowed_loss_rate),
            unit_rate: flt(contractor.default_unit_rate),
            service_item: contractor.service_item || "",
            currency: contractor.currency || frm.doc.currency,
        });
        calculate_outsourcing_totals(frm);
    },
    production_operation: set_operation_details,
    pricing_basis: calculate_outsourcing_totals,
    billing_qty: calculate_outsourcing_totals,
    unit_rate: calculate_outsourcing_totals,
});

frappe.ui.form.on("Outsourcing Processing Order Item", {
    planned_roll_count: calculate_outsourcing_totals,
    planned_weight: calculate_outsourcing_totals,
    planned_yard_qty: calculate_outsourcing_totals,
    items_remove: calculate_outsourcing_totals,
});
