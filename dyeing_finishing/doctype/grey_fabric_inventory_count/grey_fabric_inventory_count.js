/* eslint-disable */
const COUNT_CONTROLLER = "dyeing_finishing.dyeing_finishing.doctype.grey_fabric_inventory_count.grey_fabric_inventory_count";
const COUNT_METHOD = `${COUNT_CONTROLLER}.get_inventory_count_rows`;

function calculate_row(row) {
	row.difference_roll_count = flt(row.actual_roll_count) - flt(row.system_roll_count);
	row.difference_qty = flt(row.actual_qty) - flt(row.system_qty);
	if (!row.difference_reason && (row.difference_roll_count || row.difference_qty)) {
		row.difference_reason = row.difference_roll_count > 0 || row.difference_qty > 0 ? "盘盈" : "盘亏";
	}
	if (!row.difference_roll_count && !row.difference_qty) row.difference_reason = "";
}

function calculate_totals(frm) {
	const rows = frm.doc.items || [];
	const total = field => rows.reduce((sum, row) => sum + flt(row[field]), 0);
	[
		"system_roll_count", "actual_roll_count", "difference_roll_count",
		"system_qty", "actual_qty", "difference_qty",
	].forEach(field => frm.doc[`total_${field}`] = total(field));
	frm.refresh_fields([
		"total_system_roll_count", "total_actual_roll_count", "total_difference_roll_count",
		"total_system_qty", "total_actual_qty", "total_difference_qty",
	]);
}

function configure_grid(frm) {
	frm.set_df_property("items", "cannot_add_rows", true);
	frm.set_df_property("items", "cannot_delete_rows", true);
	frm.fields_dict.items?.grid?.refresh();
}

async function load_inventory(frm) {
	if (!frm.doc.warehouse) {
		frappe.msgprint(__("请先选择盘点仓库/货位。"));
		return;
	}
	const response = await frappe.call({
		method: COUNT_METHOD,
		args: {warehouse: frm.doc.warehouse, customer: frm.doc.customer},
		freeze: true,
		freeze_message: __("正在读取胚布账面库存…"),
	});
	const result = response.message || {};
	frm.clear_table("items");
	(result.items || []).forEach(values => Object.assign(frm.add_child("items"), values));
	await frm.set_value("snapshot_at", result.snapshot_at || frappe.datetime.now_datetime());
	frm.refresh_field("items");
	calculate_totals(frm);
	if (!(result.items || []).length) frappe.msgprint(__("当前范围没有可盘点的胚布库存。"));
}

function clear_snapshot(frm) {
	if (!frm.is_new() || !(frm.doc.items || []).length) return;
	frm.clear_table("items");
	frm.set_value("snapshot_at", null);
	frm.refresh_field("items");
	calculate_totals(frm);
}

function can_review_inventory_count() {
	return ["Stock Manager", "System Manager"].some(role => frappe.user_roles.includes(role));
}

function review_inventory_count(frm, action) {
	const is_reject = action === "reject_inventory_count";
	frappe.prompt([
		{
			fieldname: "review_remark",
			fieldtype: "Small Text",
			label: __("审核意见"),
			reqd: is_reject,
		},
	], async values => {
		await frappe.call({
			method: `${COUNT_CONTROLLER}.${action}`,
			args: {name: frm.doc.name, review_remark: values.review_remark},
			freeze: true,
			freeze_message: is_reject ? __("正在驳回盘点差异…") : __("正在审核并生成库存盘点凭证…"),
		});
		await frm.reload_doc();
	}, is_reject ? __("驳回盘点差异") : __("审核通过"), is_reject ? __("确认驳回") : __("确认审核"));
}

frappe.ui.form.on("Grey Fabric Inventory Count", {
	setup(frm) {
		frm.set_query("warehouse", () => ({query: `${COUNT_CONTROLLER}.get_grey_fabric_warehouses`}));
	},
	async onload(frm) {
		const posting_time = String(frm.doc.posting_time || "");
		if (frm.is_new() && (!posting_time || posting_time.toLowerCase().includes("nan"))) {
			await frm.set_value("posting_time", new Date().toTimeString().slice(0, 8));
		}
		if (frm.is_new() && !frm.doc.warehouse) {
			const warehouse = frappe.boot.dyeing_system_settings?.grey_fabric_warehouse || "胚布仓库 - 沅泰";
			await frm.set_value("warehouse", warehouse);
		}
	},
	refresh(frm) {
		configure_grid(frm);
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button((frm.doc.items || []).length ? __("重新读取账面库存") : __("读取账面库存"), () => load_inventory(frm));
		}
		if (frm.doc.docstatus === 1 && frm.doc.status === "待审核" && can_review_inventory_count()) {
			frm.add_custom_button(__("审核通过"), () => review_inventory_count(frm, "approve_inventory_count"), __("差异审核"));
			frm.add_custom_button(__("驳回"), () => review_inventory_count(frm, "reject_inventory_count"), __("差异审核"));
		}
		frm.add_custom_button(__("盘点差异查询"), () => frappe.set_route("query-report", "Grey Fabric Inventory Count Difference", {inventory_count: frm.doc.name}));
		if (frm.doc.stock_reconciliation) frm.add_custom_button(__("查看库存盘点凭证"), () => frappe.set_route("Form", "Stock Reconciliation", frm.doc.stock_reconciliation), __("库存凭证"));
		if (frm.doc.receipt_stock_entry) frm.add_custom_button(__("查看盘盈凭证"), () => frappe.set_route("Form", "Stock Entry", frm.doc.receipt_stock_entry), __("库存凭证"));
		if (frm.doc.issue_stock_entry) frm.add_custom_button(__("查看盘亏凭证"), () => frappe.set_route("Form", "Stock Entry", frm.doc.issue_stock_entry), __("库存凭证"));
	},
	async warehouse(frm) {
		clear_snapshot(frm);
		if (frm.doc.docstatus === 0 && frm.doc.customer && frm.doc.warehouse) await load_inventory(frm);
	},
	async customer(frm) {
		clear_snapshot(frm);
		if (frm.doc.docstatus === 0 && frm.doc.customer && frm.doc.warehouse) await load_inventory(frm);
	},
	items_remove(frm) { calculate_totals(frm); },
});

frappe.ui.form.on("Grey Fabric Inventory Count Item", {
	actual_roll_count(frm, cdt, cdn) {
		calculate_row(locals[cdt][cdn]);
		frm.refresh_field("items");
		calculate_totals(frm);
	},
	actual_qty(frm, cdt, cdn) {
		calculate_row(locals[cdt][cdn]);
		frm.refresh_field("items");
		calculate_totals(frm);
	},
});
