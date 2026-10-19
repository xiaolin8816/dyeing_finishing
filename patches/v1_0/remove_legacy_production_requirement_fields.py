import frappe


LEGACY_FIELDS = ("rework_requirements", "production_remarks")


def execute():
    if not frappe.db.has_column("Production Flow Card", "production_requirements"):
        return

    for fieldname in LEGACY_FIELDS:
        if not frappe.db.has_column("Production Flow Card", fieldname):
            continue
        frappe.db.sql(
            f"""UPDATE `tabProduction Flow Card`
                SET production_requirements = COALESCE(
                    NULLIF(production_requirements, ''), NULLIF(`{fieldname}`, ''), ''
                )"""
        )
        frappe.db.sql_ddl(
            f"ALTER TABLE `tabProduction Flow Card` DROP COLUMN `{fieldname}`"
        )

    frappe.db.delete(
        "DocField",
        {"parent": "Production Flow Card", "fieldname": ["in", LEGACY_FIELDS]},
    )
    frappe.clear_cache(doctype="Production Flow Card")
