from collections import defaultdict

import frappe
from frappe.utils import getdate


def execute():
	counters = defaultdict(int)
	for name in frappe.get_all("Machine Production Calendar", filters={"name": ["like", "TW-%"]}, pluck="name"):
		parts = name.split("-")
		if len(parts) == 3 and parts[2].isdigit():
			counters[parts[1]] = max(counters[parts[1]], int(parts[2]))

	legacy_rows = frappe.get_all(
		"Machine Production Calendar",
		filters={"name": ["not like", "TW-%"]},
		fields=["name", "start_datetime"],
		order_by="start_datetime, creation, name",
	)
	for row in legacy_rows:
		date_key = getdate(row.start_datetime).strftime("%y%m%d")
		counters[date_key] += 1
		new_name = f"TW-{date_key}-{counters[date_key]:03d}"
		frappe.rename_doc("Machine Production Calendar", row.name, new_name, force=True)
		frappe.db.set_value(
			"Machine Production Calendar", new_name, "maintenance_no", new_name, update_modified=False
		)
