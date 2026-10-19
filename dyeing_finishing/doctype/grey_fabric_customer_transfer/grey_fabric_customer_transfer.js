/* eslint-disable */
const METHOD = "dyeing_finishing.dyeing_finishing.doctype.grey_fabric_customer_transfer.grey_fabric_customer_transfer";

function update_totals(frm) {
	const rows = frm.doc.items || [];
	frm.set_value("total_roll_count", rows.reduce((sum, row) => sum + cint(row.transfer_roll_count), 0));
	frm.set_value("total_weight", rows.reduce((sum, row) => sum + flt(row.transfer_qty), 0));
}

function refresh_selector(frm) {
	frm.set_df_property("items", "cannot_add_rows", true);
	frm.fields_dict.items?.grid?.refresh();
	const field = frm.get_field("select_batches_html");
	if (!field?.$wrapper) return;
	const disabled = frm.doc.docstatus !== 0 || !frm.doc.source_customer;
	field.$wrapper.show().html(`<button class="btn btn-sm btn-primary select-grey-batches" ${disabled ? "disabled" : ""}>选择可过户胚布批次</button><span class="text-muted ml-2">只显示原客户有实际库存、且未在本单选择的批次。</span>`);
	field.$wrapper.off("click.greyTransfer").on("click.greyTransfer", ".select-grey-batches", () => select_batches(frm));
}

function reset_amended_inventory_links(frm) {
	if (!frm.is_new() || !frm.doc.amended_from) return;
	frm.doc.stock_entry = null;
	frm.doc.confirmed_at = null;
	(frm.doc.items || []).forEach(row => { row.target_batch_no = null; });
	frm.refresh_fields(["stock_entry", "confirmed_at", "items"]);
}

async function set_customer_name(frm, field, name_field) {
	if (!frm.doc[field]) return frm.set_value(name_field, "");
	const value = await frappe.db.get_value("Customer", frm.doc[field], "customer_name");
	await frm.set_value(name_field, value.message?.customer_name || frm.doc[field]);
}

function select_batches(frm) {
	const selected = new Set((frm.doc.items || []).map(row => row.source_batch_no).filter(Boolean));
	const dialog = new frappe.ui.form.MultiSelectDialog({
		doctype: "Batch", target: frm, setters: {}, add_filters_group: false,
		columns: ["胚布名称", "库存匹数", "库存重量(Kg)", "仓库/货位"],
		primary_action_label: "添加所选批次",
		get_query: () => ({query: `${METHOD}.get_available_batches`, filters: {customer: frm.doc.source_customer, excluded_names: JSON.stringify([...selected])}}),
		async action(selections) {
			const names = selections.filter(name => !selected.has(name));
			if (!names.length) return dialog.dialog.hide();
			const response = await frappe.call({method: `${METHOD}.get_batch_details`, args: {names, customer: frm.doc.source_customer}, freeze: true, freeze_message: "正在读取胚布库存…"});
			(response.message || []).forEach(source => {
				const row = frm.add_child("items");
				Object.assign(row, source, {source_batch_no: source.batch_no, transfer_roll_count: cint(source.stock_roll_count), transfer_qty: flt(source.stock_qty), remaining_roll_count: 0, remaining_qty: 0});
			});
			frm.refresh_field("items"); update_totals(frm); dialog.dialog.hide(); refresh_selector(frm);
		}
	});
	dialog.page_length = 1000;
	dialog.dialog.set_title("选择可过户胚布批次");
	dialog.dialog.fields_dict.search_term?.$wrapper.hide();
}

frappe.ui.form.on("Grey Fabric Customer Transfer", {
	setup(frm) { reset_amended_inventory_links(frm); frm.set_query("target_customer", () => ({filters: {name: ["!=", frm.doc.source_customer || ""]}})); },
	refresh(frm) { reset_amended_inventory_links(frm); refresh_selector(frm); },
	async source_customer(frm) { frm.clear_table("items"); frm.refresh_field("items"); update_totals(frm); await set_customer_name(frm, "source_customer", "source_customer_name"); refresh_selector(frm); },
	async target_customer(frm) { await set_customer_name(frm, "target_customer", "target_customer_name"); },
	items_remove(frm) { update_totals(frm); refresh_selector(frm); }
});

frappe.ui.form.on("Grey Fabric Customer Transfer Item", {
	transfer_roll_count(frm, cdt, cdn) { const row=locals[cdt][cdn]; row.remaining_roll_count=Math.max(0,cint(row.stock_roll_count)-cint(row.transfer_roll_count)); frm.refresh_field("items"); update_totals(frm); },
	transfer_qty(frm, cdt, cdn) { const row=locals[cdt][cdn]; row.remaining_qty=Math.max(0,flt(row.stock_qty)-flt(row.transfer_qty)); frm.refresh_field("items"); update_totals(frm); }
});
