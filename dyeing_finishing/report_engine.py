import frappe


STANDARD_PAPER_FORMATS = (
	{"paper_name": "A3纵向", "width_mm": 297, "height_mm": 420, "margin": 10, "grid_mm": 5},
	{"paper_name": "A4纵向", "width_mm": 210, "height_mm": 297, "margin": 10, "grid_mm": 5},
	{"paper_name": "A4横向", "width_mm": 297, "height_mm": 210, "margin": 10, "grid_mm": 5},
	{"paper_name": "A5纵向", "width_mm": 148, "height_mm": 210, "margin": 8, "grid_mm": 5},
	{"paper_name": "Letter纵向", "width_mm": 215.9, "height_mm": 279.4, "margin": 10, "grid_mm": 5},
	{"paper_name": "Legal纵向", "width_mm": 215.9, "height_mm": 355.6, "margin": 10, "grid_mm": 5},
	{"paper_name": "中一刀", "width_mm": 215, "height_mm": 140, "margin_top_mm": 2,
		"margin_bottom_mm": 2, "margin_left_mm": 5, "margin_right_mm": 5, "grid_mm": 1},
	{"paper_name": "60×80mm标签纸", "width_mm": 60, "height_mm": 80, "margin": 1.5,
		"grid_mm": 0.5, "label_gap_mm": 0},
)


def ensure_standard_paper_formats():
	"""Create missing standards without overwriting customer-adjusted formats."""
	if not frappe.db.exists("DocType", "Dyeing Paper Format"):
		return []
	created = []
	for values in STANDARD_PAPER_FORMATS:
		name = values["paper_name"]
		if frappe.db.exists("Dyeing Paper Format", name):
			continue
		margin = values.get("margin", 0)
		frappe.get_doc({
			"doctype": "Dyeing Paper Format", "paper_name": name, "enabled": 1, "system_standard": 1,
			"width_mm": values["width_mm"], "height_mm": values["height_mm"],
			"grid_mm": values.get("grid_mm", 1),
			"margin_top_mm": values.get("margin_top_mm", margin),
			"margin_bottom_mm": values.get("margin_bottom_mm", margin),
			"margin_left_mm": values.get("margin_left_mm", margin),
			"margin_right_mm": values.get("margin_right_mm", margin),
			"label_gap_mm": values.get("label_gap_mm", 0),
		}).insert(ignore_permissions=True)
		created.append(name)
	return created


def initialize_report_engine():
	"""Idempotent installation/migration bootstrap for the integrated report engine."""
	created_papers = ensure_standard_paper_formats()
	if not frappe.db.exists("DocType", "Crispy Format"):
		return {"paper_formats": created_papers, "crispy_print": False}
	from dyeing_finishing.dyeing_finishing.page.dyeing_print_template_manager import dyeing_print_template_manager as manager
	missing_label = not frappe.db.exists("Crispy Format", "成品空白标签 60×80mm")
	missing_delivery = not frappe.db.exists("Crispy Format", "成品出货单 215×140mm")
	created_formats = manager._ensure_crispy_pilots()
	# Apply standards only on first creation; never overwrite an existing customer layout.
	if missing_label:
		manager.apply_blank_label_standard()
	if frappe.db.exists("DocType", "Finished Product Delivery") and missing_delivery:
		manager.apply_finished_delivery_standard()
	for name in created_formats:
		if name != "成品空白标签 60×80mm":
			manager.initialize_visual_designer(name)
	return {"paper_formats": created_papers, "crispy_formats": created_formats, "crispy_print": True}
