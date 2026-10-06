import frappe


@frappe.whitelist()
def get_uom_conv_factor(uom=None, stock_uom=None):
	"""Keep Item UOM conversion compatible with requests missing stock_uom."""
	from erpnext.stock.doctype.item.item import get_uom_conv_factor as erpnext_get_uom_conv_factor

	return erpnext_get_uom_conv_factor(uom, stock_uom or uom)
