import frappe


def execute():
    if not frappe.db.has_column("Production Flow Card", "production_requirements"):
        return
    legacy_fields = [
        fieldname for fieldname in ("rework_requirements", "production_remarks")
        if frappe.db.has_column("Production Flow Card", fieldname)
    ]
    if not legacy_fields:
        return
    fallback_values = ",\n               ".join(
        f"NULLIF(`{fieldname}`, '')" for fieldname in legacy_fields
    )
    frappe.db.sql(
        f"""UPDATE `tabProduction Flow Card`
           SET production_requirements = COALESCE(
               NULLIF(production_requirements, ''),
               {fallback_values},
               ''
           )"""
    )
