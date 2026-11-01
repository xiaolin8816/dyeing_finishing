import frappe
from frappe import _


@frappe.whitelist()
def get_uom_conv_factor(uom=None, stock_uom=None):
	"""Keep Item UOM conversion compatible with requests missing stock_uom."""
	from erpnext.stock.doctype.item.item import get_uom_conv_factor as erpnext_get_uom_conv_factor

	return erpnext_get_uom_conv_factor(uom, stock_uom or uom)


@frappe.whitelist()
def get_document_print_templates(doctype, docname=None):
	"""Compatibility proxy for callers created before the printer was split out."""
	from visual_print.api import get_document_print_templates as get_templates

	return get_templates(doctype, docname)
