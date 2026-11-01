frappe.listview_settings["Grey Fabric Inventory Count"] = {
	add_fields: [
		"count_date", "warehouse", "customer_name", "batch_summary", "item_name_summary",
		"total_system_roll_count", "total_actual_roll_count", "total_system_qty", "total_actual_qty",
		"total_difference_roll_count", "total_difference_qty", "difference_reason_summary",
		"status", "docstatus",
	],

	onload(listview) {
		// A workspace route can occasionally leave the list shell visible without
		// starting its first data request. Retry once, but only while this list is
		// still the active route and the native renderer has no rows.
		window.setTimeout(() => {
			const route = frappe.get_route() || [];
			const is_active_list = route[0] === "List" && route[1] === "Grey Fabric Inventory Count";
			const has_rows = (listview.data || []).length > 0;
			const has_rendered_rows = listview.$result?.find(".list-row-container:not(:has(.list-row-head))").length > 0;

			if (is_active_list && !has_rows && !has_rendered_rows && !listview.__grey_fabric_count_retry_started) {
				listview.__grey_fabric_count_retry_started = true;
				listview.last_args = null;
				listview.refresh();
			}
		}, 1800);

	},

	get_indicator(doc) {
		if (doc.status === "已审核") return [__("已审核"), "green", "status,=,已审核"];
		if (doc.status === "待审核") return [__("待审核"), "orange", "status,=,待审核"];
		if (doc.status === "已驳回") return [__("已驳回"), "red", "status,=,已驳回"];
		if (doc.docstatus === 2) return [__("已取消"), "red", "docstatus,=,2"];
		return [__("草稿"), "orange", "docstatus,=,0"];
	},
};
