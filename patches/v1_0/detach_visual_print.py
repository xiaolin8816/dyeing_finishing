import frappe


TEST_FORMATS = (
	"生产流转卡 A4",
	"成品空白标签 60×80mm",
	"成品出货单 215×140mm",
	"成品包装入库单",
)

REQUIRED_PAPER_FORMATS = (
	{
		"paper_name": "60×80mm标签纸", "width_mm": 60, "height_mm": 80,
		"orientation": "纵向", "grid_mm": 0.5,
		"margin_top_mm": 1.5, "margin_bottom_mm": 1.5,
		"margin_left_mm": 1.5, "margin_right_mm": 1.5,
	},
	{
		"paper_name": "中一刀", "width_mm": 215, "height_mm": 140,
		"orientation": "横向", "grid_mm": 1,
		"margin_top_mm": 2, "margin_bottom_mm": 2,
		"margin_left_mm": 5, "margin_right_mm": 5,
	},
)


def execute():
	"""Move reusable paper sizes to visual_print and remove the three approved test formats."""
	if frappe.db.exists("DocType", "Visual Print Paper Format") and frappe.db.exists("DocType", "Dyeing Paper Format"):
		fields = [
			"paper_name", "enabled", "system_standard", "width_mm", "height_mm", "orientation", "grid_mm",
			"margin_top_mm", "margin_bottom_mm", "margin_left_mm", "margin_right_mm", "label_gap_mm", "remarks",
		]
		for row in frappe.get_all("Dyeing Paper Format", fields=fields):
			if frappe.db.exists("Visual Print Paper Format", row.paper_name):
				continue
			payload = {key: row.get(key) for key in fields}
			payload.update({"doctype": "Visual Print Paper Format"})
			frappe.get_doc(payload).insert(ignore_permissions=True)

	if frappe.db.exists("DocType", "Visual Print Paper Format"):
		for paper in REQUIRED_PAPER_FORMATS:
			if frappe.db.exists("Visual Print Paper Format", paper["paper_name"]):
				frappe.db.set_value(
					"Visual Print Paper Format", paper["paper_name"], "system_standard", 0,
					update_modified=False,
				)
				continue
			frappe.get_doc({
				"doctype": "Visual Print Paper Format",
				"enabled": 1,
				"system_standard": 0,
				"label_gap_mm": 0,
				**paper,
			}).insert(ignore_permissions=True)

	if frappe.db.exists("DocType", "Crispy Template"):
		frappe.db.delete("Crispy Template", {"source_crispy_format": ["in", TEST_FORMATS]})
	if frappe.db.exists("DocType", "Crispy Format"):
		frappe.db.delete("Crispy Format", {"name": ["in", TEST_FORMATS]})
