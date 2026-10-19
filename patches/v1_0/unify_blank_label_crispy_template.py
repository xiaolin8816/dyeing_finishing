import frappe


def execute():
	"""Keep only the visual Crispy blank-label template on installed sites."""
	if not frappe.db.exists("DocType", "Crispy Format"):
		return

	if frappe.db.exists("Print Format", "成品空白标签"):
		frappe.delete_doc("Print Format", "成品空白标签", force=True, ignore_permissions=True)

	from dyeing_finishing.dyeing_finishing.page.dyeing_print_template_manager.dyeing_print_template_manager import (
		apply_blank_label_standard,
	)

	apply_blank_label_standard()

