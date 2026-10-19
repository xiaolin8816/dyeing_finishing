import frappe


WORK_CENTERS = {
	"WC-DYE": ("染色工段", "设备中心"),
}

DEFAULT_RESOURCES = {}


def operation_rule(name):
	name = (name or "").strip()
	if any(word in name for word in ("前处理", "染色", "后处理", "除油")):
		return "设备排程", "WC-DYE", "染缸"
	return "仅记录进度", None, None


def insert_if_missing(doctype, name, values):
	if frappe.db.exists(doctype, name):
		return
	frappe.get_doc({"doctype": doctype, "name": name, **values}).insert(ignore_permissions=True)


def execute():
	for code, (name, center_type) in WORK_CENTERS.items():
		insert_if_missing("Production Work Center", code, {
			"work_center_code": code, "work_center_name": name,
			"work_center_type": center_type, "capacity_uom": "Kg", "status": "启用",
		})

	legacy_machines = frappe.get_all("Dyeing Machine", fields=["*"]) if frappe.db.exists("DocType", "Dyeing Machine") else []
	for machine in legacy_machines:
		resource_code = f"RES-{machine.name}"
		insert_if_missing("Production Resource", resource_code, {
			"resource_code": resource_code, "resource_name": machine.machine_name,
			"status": machine.status, "work_center": "WC-DYE", "resource_type": "染缸", "resource_mode": "设备",
			"minimum_capacity": machine.minimum_capacity, "rated_capacity": machine.capacity,
			"maximum_capacity": machine.maximum_capacity, "capacity_uom": machine.capacity_uom,
			"hourly_capacity": machine.hourly_capacity, "setup_minutes": machine.setup_minutes,
			"cleaning_minutes": machine.cleaning_minutes, "allow_rework": machine.allow_rework,
			"source_dyeing_machine": machine.name, "workstation": machine.workstation,
		})

	for resource_type, (code, name, center, mode) in DEFAULT_RESOURCES.items():
		insert_if_missing("Production Resource", code, {
			"resource_code": code, "resource_name": name, "status": "启用",
			"work_center": center, "resource_type": resource_type, "resource_mode": mode,
			"capacity_uom": "Kg", "allow_rework": 1,
		})

	rules = {}
	for operation in frappe.get_all("Production Operation", fields=["name", "production_operation_name"]):
		rule = operation_rule(operation.production_operation_name)
		rules[operation.name] = rule
		frappe.db.set_value("Production Operation", operation.name, {
			"scheduling_mode": rule[0], "default_work_center": rule[1], "resource_type": rule[2],
		}, update_modified=False)

	legacy_schedule_field = frappe.db.has_column("Dyeing Production Schedule Item", "dyeing_machine")
	fields = ["name", "operation"] + (["dyeing_machine"] if legacy_schedule_field else [])
	for row in frappe.get_all("Dyeing Production Schedule Item", fields=fields):
		mode, center, resource_type = rules.get(row.operation, ("仅记录进度", None, None))
		if resource_type == "染缸":
			legacy_machine = row.get("dyeing_machine") if legacy_schedule_field else None
			resource = f"RES-{legacy_machine}" if legacy_machine else None
		else:
			resource = DEFAULT_RESOURCES.get(resource_type, (None,))[0]
		resource_name = frappe.db.get_value("Production Resource", resource, "resource_name") if resource else None
		frappe.db.set_value("Dyeing Production Schedule Item", row.name, {
			"scheduling_mode": mode, "work_center": center, "resource_type": resource_type,
			"production_resource": resource, "resource_name": resource_name,
		}, update_modified=False)

	for row in frappe.get_all("Production Flow Card Operation", fields=["name", "production_schedule", "operation"]):
		if not row.production_schedule:
			continue
		item = frappe.db.get_value("Dyeing Production Schedule Item", {
			"parent": row.production_schedule, "operation": row.operation,
		}, ["production_resource", "resource_name"], as_dict=True)
		if item:
			frappe.db.set_value("Production Flow Card Operation", row.name, item, update_modified=False)

	calendar_has_legacy_field = frappe.db.has_column("Machine Production Calendar", "dyeing_machine")
	calendar_fields = ["name"] + (["dyeing_machine"] if calendar_has_legacy_field else [])
	for row in frappe.get_all("Machine Production Calendar", fields=calendar_fields):
		if calendar_has_legacy_field and row.dyeing_machine:
			frappe.db.set_value("Machine Production Calendar", row.name,
				"production_resource", f"RES-{row.dyeing_machine}", update_modified=False)

	frappe.db.commit()
