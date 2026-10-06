import frappe
from frappe.custom.doctype.custom_field.custom_field import delete_custom_fields


RECEIPT_TYPE_FIELD = "Purchase Receipt-custom_dyeing_receipt_type"
SECTION_FIELD = "custom_dyeing_receipt_section"


def execute():
    if frappe.db.exists("Custom Field", RECEIPT_TYPE_FIELD):
        frappe.db.set_value("Custom Field", RECEIPT_TYPE_FIELD, "insert_after", "return_against")

    delete_custom_fields({"Purchase Receipt": [SECTION_FIELD]})
    frappe.clear_cache(doctype="Purchase Receipt")
