/* eslint-disable */
const METHOD = "dyeing_finishing.dyeing_finishing.doctype.customer_grey_fabric_return.customer_grey_fabric_return";

function update_totals(frm) {
	const rows = frm.doc.items || [];
	frm.set_value("total_batch_count", rows.length);
	frm.set_value("total_roll_count", rows.reduce((sum, row) => sum + cint(row.return_roll_count), 0));
	frm.set_value("total_weight", rows.reduce((sum, row) => sum + flt(row.return_qty), 0));
}

function refresh_selector(frm) {
	frm.set_df_property("items", "cannot_add_rows", true);
	frm.fields_dict.items?.grid?.refresh();
	const field = frm.get_field("select_batches_html");
	if (!field?.$wrapper) return;
	const disabled = frm.doc.docstatus !== 0 || !frm.doc.customer;
	field.$wrapper.show().html(`<button class="btn btn-sm btn-primary select-return-batches" ${disabled ? "disabled" : ""}>选择可退胚布批次</button><span class="text-muted ml-2">只显示当前客户在胚布仓有实际库存、且未在本单选择的批次。</span>`);
	field.$wrapper.off("click.greyReturn").on("click.greyReturn", ".select-return-batches", () => select_batches(frm));
}

function reset_amended_links(frm) {
	if (!frm.is_new() || !frm.doc.amended_from) return;
	frm.doc.stock_entry = null;
	frm.doc.confirmed_at = null;
	frm.refresh_fields(["stock_entry", "confirmed_at"]);
}

function select_batches(frm) {
	const selected = new Set((frm.doc.items || []).map(row => row.batch_no).filter(Boolean));
	const dialog = new frappe.ui.form.MultiSelectDialog({
		doctype: "Batch", target: frm, setters: {}, add_filters_group: false,
		columns: ["胚布名称", "库存匹数", "库存数量", "仓库/货位"], primary_action_label: "添加所选批次",
		get_query: () => ({query: `${METHOD}.get_available_batches`, filters: {customer: frm.doc.customer, excluded_names: JSON.stringify([...selected])}}),
		async action(selections) {
			const names = selections.filter(name => !selected.has(name));
			if (!names.length) return dialog.dialog.hide();
			const response = await frappe.call({method: `${METHOD}.get_batch_details`, args: {names, customer: frm.doc.customer}, freeze: true, freeze_message: "正在读取胚布库存…"});
			(response.message || []).forEach(source => {
				const row = frm.add_child("items");
				Object.assign(row, source, {batch_no: source.batch_no, return_roll_count: cint(source.stock_roll_count), return_qty: flt(source.stock_qty), remaining_roll_count: 0, remaining_qty: 0});
			});
			frm.refresh_field("items"); update_totals(frm); dialog.dialog.hide(); refresh_selector(frm);
		}
	});
	dialog.page_length = 1000;
	dialog.dialog.set_title("选择可退胚布批次");
	dialog.dialog.fields_dict.search_term?.$wrapper.hide();
}

frappe.ui.form.on("Customer Grey Fabric Return", {
	setup(frm) { reset_amended_links(frm); },
	refresh(frm) { reset_amended_links(frm); refresh_selector(frm); },
	async customer(frm) {
		frm.clear_table("items"); frm.refresh_field("items"); update_totals(frm);
		if (!frm.doc.customer) await frm.set_value("customer_name", "");
		else {
			const value = await frappe.db.get_value("Customer", frm.doc.customer, "customer_name");
			await frm.set_value("customer_name", value.message?.customer_name || frm.doc.customer);
		}
		refresh_selector(frm);
	},
	items_remove(frm) { update_totals(frm); refresh_selector(frm); }
});

frappe.ui.form.on("Customer Grey Fabric Return Item", {
	return_roll_count(frm, cdt, cdn) { const row=locals[cdt][cdn]; row.remaining_roll_count=Math.max(0,flt(row.stock_roll_count)-cint(row.return_roll_count)); frm.refresh_field("items"); update_totals(frm); },
	return_qty(frm, cdt, cdn) { const row=locals[cdt][cdn]; row.remaining_qty=Math.max(0,flt(row.stock_qty)-flt(row.return_qty)); frm.refresh_field("items"); update_totals(frm); }
});
