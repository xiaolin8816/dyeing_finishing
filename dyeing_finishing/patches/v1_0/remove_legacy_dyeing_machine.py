import frappe


LEGACY_COLUMNS = (
	("Site Dyeing Material Sheet", "dyeing_machine"),
	("Site Dyeing Material Issue", "dyeing_machine"),
	("Production Flow Card Progress", "dyeing_machine"),
	("Production Flow Card Operation", "dyeing_machine"),
	("Dyeing Production Schedule Item", "dyeing_machine"),
	("Machine Production Calendar", "dyeing_machine"),
	("Production Resource", "source_dyeing_machine"),
)


def execute():
	"""Remove test-stage legacy machine data after Production Resource consolidation."""
	for doctype, fieldname in LEGACY_COLUMNS:
		table = f"tab{doctype}"
		if frappe.db.table_exists(doctype) and _column_exists(table, fieldname):
			frappe.db.sql_ddl(f"ALTER TABLE `{table}` DROP COLUMN `{fieldname}`")

	if frappe.db.exists("DocType", "Dyeing Machine"):
		frappe.db.delete("Dyeing Machine")
	if frappe.db.table_exists("Dyeing Machine"):
		frappe.db.sql_ddl("DROP TABLE `tabDyeing Machine`")

	frappe.clear_cache()


def _column_exists(table, column):
	return bool(frappe.db.sql(f"SHOW COLUMNS FROM `{table}` LIKE %s", column))
