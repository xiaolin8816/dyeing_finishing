frappe.ui.form.on("Customer Grey Fabric Receipt", {
	setup(frm) {
		frm.set_query("target_warehouse", () => ({
			filters: {
				name: "胚布仓库 - 沅泰",
				is_group: 0,
				disabled: 0,
			},
		}));

		frm.set_query("target_location", "items", () => ({
			filters: {
				parent_warehouse: "胚布货位 - 沅泰",
				is_group: 0,
				disabled: 0,
			},
		}));
	},
});