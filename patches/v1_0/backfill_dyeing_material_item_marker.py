import frappe


def execute():
	"""为现有染料、助剂物料补齐染化料档案标记。"""
	frappe.db.set_value(
		"Item",
		{"item_group": ["in", ["染料", "助剂"]]},
		"custom_is_dyeing_material",
		1,
		update_modified=False,
	)
