const ENERGY_ALLOCATION_METHOD = "dyeing_finishing.dyeing_finishing.doctype.dyeing_energy_allocation.dyeing_energy_allocation.get_allocation_preview";

function apply_energy_allocation_layout(frm) {
    ["document_section", "basis_section"].forEach((fieldname) => {
        frm.get_field(fieldname)?.wrapper?.addClass("dyeing-responsive-form-grid");
    });
    frm.get_field("items")?.$wrapper?.find(".grid-field > .control-label").first().hide();
}

async function generate_energy_allocation(frm) {
    if (!frm.doc.source_reading) return;
    const source = frm.doc.source_reading;
    const basis = frm.doc.allocation_basis;
    const rate = frm.doc.rate_standard || "";
    const response = await frappe.call({
        method: ENERGY_ALLOCATION_METHOD,
        args: {source_reading: source, allocation_basis: basis, rate_standard: rate},
        freeze: true,
        freeze_message: "正在计算能源分摊…",
    });
    if (frm.doc.source_reading !== source || frm.doc.allocation_basis !== basis
        || (frm.doc.rate_standard || "") !== rate) return;
    const rows = response.message?.rows || [];
    frm.clear_table("items");
    rows.forEach((values) => Object.assign(frm.add_child("items"), values));
    frm.refresh_field("items");
    await frm.set_value({
        company: response.message?.company || "",
        meter_count: new Set(rows.map((row) => row.meter)).size,
        line_count: rows.length,
        total_amount: rows.reduce((sum, row) => sum + flt(row.estimated_amount), 0),
    });
    if (response.message?.source_docstatus === 0) {
        frappe.show_alert({message: "来源抄表单尚未提交，本分摊单仅可保存草稿", indicator: "orange"});
    }
}

frappe.ui.form.on("Dyeing Energy Allocation", {
    setup(frm) {
        frm.set_df_property("items", "cannot_add_rows", true);
        frm.set_df_property("items", "cannot_delete_rows", true);
        if (frm.is_new() && !frm.doc.company) {
            frm.set_value("company", frappe.defaults.get_user_default("Company") || frappe.boot.sysdefaults.company);
        }
        frm.set_query("source_reading", () => ({
            filters: {docstatus: ["in", [0, 1]], company: frm.doc.company || "__no_company__"},
        }));
        frm.set_query("rate_standard", () => ({
            filters: {docstatus: 1, company: frm.doc.company || "__no_company__"},
        }));
    },
    refresh(frm) {
        frm.set_df_property("items", "cannot_add_rows", true);
        frm.set_df_property("items", "cannot_delete_rows", true);
        apply_energy_allocation_layout(frm);
        if (frm.doc.docstatus === 0 && frm.doc.source_reading) {
            frm.add_custom_button("重新生成分摊", () => generate_energy_allocation(frm));
        }
    },
    source_reading(frm) {
        return generate_energy_allocation(frm);
    },
    allocation_basis(frm) {
        return generate_energy_allocation(frm);
    },
    rate_standard(frm) {
        return generate_energy_allocation(frm);
    },
});
