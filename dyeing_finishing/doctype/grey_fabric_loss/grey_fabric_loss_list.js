frappe.listview_settings["Grey Fabric Loss"] = {
	get_indicator(doc) {
		const colors = {
			"草稿": "gray",
			"待审核": "orange",
			"已审核": "green",
			"已驳回": "red",
			"已取消": "gray",
		};
		return [__(doc.status || "草稿"), colors[doc.status] || "gray", `status,=,${doc.status || "草稿"}`];
	},
};
