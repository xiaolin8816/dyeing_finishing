function refresh_preview_document_code(frm) {
	if (!frm.is_new() || frm.doc.document_code) return;
	frappe.call({
		method: "dyeing_finishing.dyeing_finishing.doctype.site_dyeing_material_issue.site_dyeing_material_issue.get_preview_document_code",
		args: { issue_date: frm.doc.issue_date },
		callback: ({ message }) => {
			if (message && frm.is_new() && !frm.doc.document_code) {
				frm.set_value("document_code", message);
			}
		}
	});
}

frappe.ui.form.on("Site Dyeing Material Issue", {
	setup(frm) {
		frm.set_query("material_sheet", () => ({
			filters: { docstatus: 1, material_sheet_status: ["in", ["待领料", "部分领料"]] }
		}));
	},
	onload(frm) {
		refresh_preview_document_code(frm);
	},
	issue_date(frm) {
		if (frm.is_new()) {
			frm.set_value("document_code", "").then(() => refresh_preview_document_code(frm));
		}
	},
	material_sheet(frm) {
		if (!frm.doc.material_sheet) return;
		frappe.call({
			method: "dyeing_finishing.dyeing_finishing.doctype.site_dyeing_material_issue.site_dyeing_material_issue.get_material_sheet_details",
			args: { material_sheet: frm.doc.material_sheet },
			freeze: true,
			freeze_message: "正在带出料单明细…",
			callback: ({ message }) => {
				if (!message) return;
				["production_flow_card", "sales_order", "customer_name", "color_no", "color", "finished_product_name", "dyeing_machine", "source_warehouse"].forEach(field => frm.set_value(field, message[field] || ""));
				frm.clear_table("items");
				(message.items || []).forEach(item => {
					const row = frm.add_child("items");
					Object.assign(row, item);
				});
				frm.refresh_field("items");
			}
		});
	}
});

frappe.ui.form.on("Site Dyeing Material Issue Item", {
	issue_qty_g(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "issue_qty_kg", flt(row.issue_qty_g) / 1000);
	}
});
