import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	for doctype in ("Customer", "Supplier"):
		make_property_setter(
			doctype,
			None,
			"show_title_field_in_link",
			"1",
			"Check",
			for_doctype=True,
			validate_fields_for_doctype=False,
		)
		frappe.clear_cache(doctype=doctype)
