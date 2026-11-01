/* eslint-disable */
const LOSS_METHOD = "dyeing_finishing.dyeing_finishing.doctype.grey_fabric_loss.grey_fabric_loss";

function apply_responsive_form_layout(frm) {
	frm.get_field("basic_section")?.wrapper?.addClass("dyeing-responsive-form-grid");
	frm.get_field("reason_section")?.wrapper?.addClass(
		"dyeing-responsive-form-grid dyeing-responsive-form-grid-3"
	);
}

function update_loss_totals(frm) {
	const rows = frm.doc.items || [];
	frm.set_value("total_batch_count", rows.length);
	frm.set_value("total_loss_roll_count", rows.reduce((sum, row) => sum + flt(row.loss_roll_count), 0));
	frm.set_value("total_loss_weight", rows.reduce((sum, row) => sum + flt(row.loss_qty), 0));
}

function refresh_loss_row(frm, row) {
	row.remaining_roll_count = Math.max(0, flt(row.stock_roll_count) - flt(row.loss_roll_count));
	row.remaining_qty = Math.max(0, flt(row.stock_qty) - flt(row.loss_qty));
	frm.refresh_field("items");
	update_loss_totals(frm);
}

function refresh_loss_selector(frm) {
	frm.set_df_property("items", "cannot_add_rows", true);
	frm.set_df_property("items", "cannot_delete_rows", frm.doc.docstatus !== 0);
	const grid = frm.fields_dict.items?.grid;
	grid?.refresh();
	grid?.wrapper?.children(".control-label").hide();
	const field = frm.get_field("select_batches_html");
	if (!field?.$wrapper) return;
	const disabled = frm.doc.docstatus !== 0 || !frm.doc.customer || !frm.doc.warehouse;
	field.$wrapper.show().html(`<button class="btn btn-sm btn-primary select-loss-batches" ${disabled ? "disabled" : ""}>选择报损批次</button><span class="text-muted ml-2">只显示当前客户在所选仓库中有实际库存的批次。</span>`);
	field.$wrapper.off("click.greyFabricLoss").on("click.greyFabricLoss", ".select-loss-batches", () => select_loss_batches(frm));
}

function select_loss_batches(frm) {
	const selected = new Set((frm.doc.items || []).map(row => row.batch_no).filter(Boolean));
	const dialog = new frappe.ui.form.MultiSelectDialog({
		doctype: "Batch",
		target: frm,
		setters: {},
		add_filters_group: false,
		columns: ["批次", "胚布名称", "库存匹数", "库存重量", "仓库"],
		primary_action_label: "添加所选批次",
		get_query: () => ({
			query: `${LOSS_METHOD}.get_available_batches`,
			filters: {
				customer: frm.doc.customer,
				warehouse: frm.doc.warehouse,
				excluded_names: JSON.stringify([...selected]),
			},
		}),
		async action(selections) {
			const names = selections.filter(name => !selected.has(name));
			if (!names.length) return dialog.dialog.hide();
			const response = await frappe.call({
				method: `${LOSS_METHOD}.get_batch_details`,
				args: {names, customer: frm.doc.customer, warehouse: frm.doc.warehouse},
				freeze: true,
				freeze_message: "正在读取胚布库存…",
			});
			(response.message || []).forEach(source => {
				const row = frm.add_child("items");
				Object.assign(row, source, {
					batch_no: source.batch_no,
					loss_method: "整匹报损",
					loss_roll_count: flt(source.stock_roll_count),
					loss_qty: flt(source.stock_qty),
					remaining_roll_count: 0,
					remaining_qty: 0,
				});
			});
			frm.refresh_field("items");
			update_loss_totals(frm);
			dialog.dialog.hide();
			refresh_loss_selector(frm);
		},
	});
	dialog.page_length = 1000;
	dialog.dialog.set_title("选择报损批次");
	dialog.dialog.set_df_property("search_term", "label", "批次查询");
	dialog.dialog.set_df_property("search_term", "placeholder", "输入批次或胚布名称");
	const search_field = dialog.dialog.fields_dict.search_term;
	const search_column = search_field?.$wrapper.closest(".form-column");
	search_column?.css({flex: "0 0 100%", maxWidth: "100%"});
	search_column?.siblings(".form-column").hide();
	search_field?.$wrapper.find(".input-max-width").css({maxWidth: "100%", paddingRight: 0});
	dialog.dialog.get_secondary_btn().hide();
}

function can_review_loss() {
	return ["Stock Manager", "System Manager"].some(role => frappe.user_roles.includes(role));
}

function review_loss(frm, action) {
	const reject = action === "reject_loss";
	frappe.prompt([{
		fieldname: "review_remark",
		fieldtype: "Small Text",
		label: __("审核意见"),
		reqd: reject,
	}], async values => {
		await frappe.call({
			method: `${LOSS_METHOD}.${action}`,
			args: {name: frm.doc.name, review_remark: values.review_remark},
			freeze: true,
			freeze_message: reject ? __("正在驳回胚布报损单…") : __("正在审核并生成库存出库凭证…"),
		});
		await frm.reload_doc();
	}, reject ? __("驳回胚布报损单") : __("审核通过"), reject ? __("确认驳回") : __("确认审核"));
}

function reset_loss_amendment(frm) {
	if (!frm.is_new() || !frm.doc.amended_from) return;
	frm.doc.status = "草稿";
	frm.doc.stock_entry = null;
	frm.doc.reviewed_by = null;
	frm.doc.reviewed_at = null;
	frm.doc.review_remark = null;
	frm.refresh_fields(["status", "stock_entry", "reviewed_by", "reviewed_at", "review_remark"]);
}

frappe.ui.form.on("Grey Fabric Loss", {
	setup(frm) {
		frm.set_query("warehouse", () => ({
			query: "dyeing_finishing.dyeing_finishing.doctype.grey_fabric_inventory_count.grey_fabric_inventory_count.get_grey_fabric_warehouses",
		}));
		reset_loss_amendment(frm);
	},
	async onload(frm) {
		if (frm.is_new() && !frm.doc.warehouse) {
			await frm.set_value("warehouse", frappe.boot.dyeing_system_settings?.grey_fabric_warehouse || "胚布仓库 - 沅泰");
		}
	},
	refresh(frm) {
		apply_responsive_form_layout(frm);
		reset_loss_amendment(frm);
		refresh_loss_selector(frm);
		if (frm.doc.docstatus === 1 && frm.doc.status === "待审核" && can_review_loss()) {
			frm.add_custom_button(__("审核通过"), () => review_loss(frm, "approve_loss"), __("报损审核"));
			frm.add_custom_button(__("驳回"), () => review_loss(frm, "reject_loss"), __("报损审核"));
		}
		if (frm.doc.stock_entry) {
			frm.add_custom_button(__("查看库存出库凭证"), () => frappe.set_route("Form", "Stock Entry", frm.doc.stock_entry), __("库存凭证"));
		}
	},
	async customer(frm) {
		frm.clear_table("items");
		frm.refresh_field("items");
		update_loss_totals(frm);
		refresh_loss_selector(frm);
	},
	warehouse(frm) {
		frm.clear_table("items");
		frm.refresh_field("items");
		update_loss_totals(frm);
		refresh_loss_selector(frm);
	},
	items_remove(frm) {
		update_loss_totals(frm);
		refresh_loss_selector(frm);
	},
});

frappe.ui.form.on("Grey Fabric Loss Item", {
	loss_method(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.loss_method === "整匹报损") {
			row.loss_roll_count = flt(row.stock_roll_count);
			row.loss_qty = flt(row.stock_qty);
		} else {
			row.loss_roll_count = 0;
			if (flt(row.loss_qty) >= flt(row.stock_qty)) row.loss_qty = 0;
		}
		refresh_loss_row(frm, row);
	},
	loss_roll_count(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const stockRollCount = cint(row.stock_roll_count);
		if (row.loss_method !== "整匹报损") {
			row.loss_roll_count = 0;
		} else {
			row.loss_roll_count = Math.max(0, Math.min(cint(row.loss_roll_count), stockRollCount));
			if (row.loss_roll_count < stockRollCount && flt(row.loss_qty) >= flt(row.stock_qty)) {
				row.loss_qty = 0;
			} else if (row.loss_roll_count === stockRollCount) {
				row.loss_qty = flt(row.stock_qty);
			}
		}
		refresh_loss_row(frm, row);
	},
	loss_qty(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		row.loss_qty = Math.max(0, Math.min(flt(row.loss_qty), flt(row.stock_qty)));
		if (row.loss_method === "部分重量损耗") row.loss_roll_count = 0;
		refresh_loss_row(frm, row);
	},
});
