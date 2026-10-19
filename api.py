import json

import frappe
from frappe import _
from frappe.utils import cint


@frappe.whitelist()
def get_uom_conv_factor(uom=None, stock_uom=None):
	"""Keep Item UOM conversion compatible with requests missing stock_uom."""
	from erpnext.stock.doctype.item.item import get_uom_conv_factor as erpnext_get_uom_conv_factor

	return erpnext_get_uom_conv_factor(uom, stock_uom or uom)


@frappe.whitelist()
def get_document_print_templates(doctype, docname=None):
	"""Return published visual print templates usable in a document context."""
	doctype = (doctype or "").strip()
	docname = (docname or "").strip()
	if not doctype or not frappe.db.exists("DocType", doctype):
		frappe.throw(_("无效的单据类型"))

	if docname:
		doc = frappe.get_doc(doctype, docname)
		if not doc.has_permission("read"):
			frappe.throw(_("您没有查看该单据的权限"), frappe.PermissionError)
		if doctype == "Finished Product Blank Label" and not doc.has_permission("write"):
			return []
		company = doc.get("company") if doc.meta.get_field("company") else None
	else:
		if not frappe.has_permission(doctype, "read"):
			frappe.throw(_("您没有查看该单据类型的权限"), frappe.PermissionError)
		if doctype == "Finished Product Blank Label" and not frappe.has_permission(doctype, "write"):
			return []
		company = None

	if not frappe.db.exists("DocType", "Crispy Format") or not frappe.db.exists("DocType", "Crispy Template"):
		return []

	formats = frappe.get_all(
		"Crispy Format",
		filters={"doc_type": doctype},
		fields=["name", "company", "is_default", "presentation_settings", "layout_json", "modified"],
		order_by="is_default desc, modified desc",
		ignore_permissions=True,
	)
	if not formats:
		return []

	active_formats = {
		row.source_crispy_format
		for row in frappe.get_all(
			"Crispy Template",
			filters={
				"source_crispy_format": ["in", [row.name for row in formats]],
				"is_active": 1,
				"status": "Approved",
			},
			fields=["source_crispy_format"],
			ignore_permissions=True,
		)
	}

	result = []
	for row in formats:
		if row.name not in active_formats or not row.layout_json:
			continue
		if company and row.company and row.company != company:
			continue
		page = (_as_dict(row.presentation_settings).get("page") or {})
		result.append({
			"name": row.name,
			"is_default": cint(row.is_default),
			"company": row.company or "",
			"paper": _paper_description(page),
			"requires_quantity": doctype == "Finished Product Blank Label",
		})
	return result


def _as_dict(value):
	if isinstance(value, dict):
		return value
	try:
		return json.loads(value or "{}")
	except (TypeError, ValueError):
		return {}


def _paper_description(page):
	custom_name = (page.get("custom_name") or "").strip()
	width = page.get("width_mm")
	height = page.get("height_mm")
	if width and height:
		size = f"{float(width):g}×{float(height):g} mm"
		return f"{custom_name}（{size}）" if custom_name else size
	return custom_name or page.get("size") or "默认纸张"
