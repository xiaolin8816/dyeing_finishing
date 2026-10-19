import frappe


def _resource_for_legacy_machine(machine):
	if not machine:
		return None
	return (
		frappe.db.get_value("Production Resource", {"source_dyeing_machine": machine}, "name")
		or (f"RES-{machine}" if frappe.db.exists("Production Resource", f"RES-{machine}") else None)
	)


def execute():
	"""Make Production Resource the only maintained machine master without losing history."""
	if not frappe.db.exists("DocType", "Dyeing Machine"):
		return
	for doctype in ("Site Dyeing Material Sheet", "Site Dyeing Material Issue"):
		for row in frappe.get_all(doctype, fields=["name", "dyeing_machine", "production_resource"]):
			resource = row.production_resource or _resource_for_legacy_machine(row.dyeing_machine)
			if resource and resource != row.production_resource:
				frappe.db.set_value(doctype, row.name, "production_resource", resource, update_modified=False)

	for row in frappe.get_all(
		"Production Flow Card Progress", fields=["name", "dyeing_machine", "production_resource"]
	):
		resource = row.production_resource or _resource_for_legacy_machine(row.dyeing_machine)
		if resource and resource != row.production_resource:
			frappe.db.set_value(
				"Production Flow Card Progress", row.name, "production_resource", resource, update_modified=False
			)

	frappe.db.delete("Workspace Link", {"parent": "印染基础资料", "link_to": "Dyeing Machine"})
	frappe.clear_cache()

