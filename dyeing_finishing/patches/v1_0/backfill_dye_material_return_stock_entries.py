import frappe


def execute():
    fields = [
        "name",
        "supplier",
        "return_reason",
        "stock_entry",
        "material_receipt_entry",
    ]
    returns = frappe.get_all(
        "Dye Material Return",
        filters={"docstatus": ["!=", 2]},
        fields=fields,
    )
    for return_doc in returns:
        values = {
            "custom_dyeing_return_business_type": "染料退货",
            "custom_dye_material_return": return_doc.name,
            "custom_dyeing_return_supplier": return_doc.supplier,
            "custom_dyeing_return_reason": return_doc.return_reason,
        }
        for stock_entry in (return_doc.stock_entry, return_doc.material_receipt_entry):
            if stock_entry and frappe.db.exists("Stock Entry", stock_entry):
                frappe.db.set_value("Stock Entry", stock_entry, values, update_modified=False)
