import frappe


DYEING_OPERATION_NAMES = {"前处理", "染色", "后处理", "除油"}

PLACEHOLDER_RESOURCES = (
	"RES-DEWATER-01",
	"RES-FINISH-01",
	"RES-INSPECT-01",
	"RES-LOOSEN-01",
	"RES-OPEN-01",
	"RES-PACK-01",
	"RES-SEAM-01",
	"RES-SETTING-01",
	"RES-WASH-DRY-01",
)

UNUSED_WORK_CENTERS = (
	"WC-DEWATER",
	"WC-FINISH",
	"WC-INSPECT",
	"WC-LOOSEN",
	"WC-OPEN",
	"WC-PACK",
	"WC-SEAM",
	"WC-SETTING",
	"WC-WASH-DRY",
)


def execute():
	# The first production-board prototype created generic machines for every
	# operation.  The simplified board schedules only the dyeing bottleneck;
	# all other operations continue to be recorded on the flow card.
	for operation in frappe.get_all(
		"Production Operation", fields=["name", "production_operation_name"]
	):
		operation_name = (operation.production_operation_name or "").strip()
		if operation_name == "预定":
			frappe.db.set_value(
				"Production Operation",
				operation.name,
				"production_operation_name",
				"预定型",
				update_modified=False,
			)
			operation_name = "预定型"

		if operation_name in DYEING_OPERATION_NAMES:
			values = {
				"scheduling_mode": "设备排程",
				"default_work_center": "WC-DYE",
				"resource_type": "染缸",
			}
		else:
			values = {
				"scheduling_mode": "仅记录进度",
				"default_work_center": None,
				"resource_type": None,
			}
		frappe.db.set_value("Production Operation", operation.name, values, update_modified=False)

	frappe.db.sql("""
		UPDATE `tabProduction Flow Card Operation`
		SET operation_name='预定型'
		WHERE TRIM(operation_name)='预定'
	""")

	for name in PLACEHOLDER_RESOURCES:
		if frappe.db.exists("Production Resource", name):
			frappe.delete_doc("Production Resource", name, force=True, ignore_permissions=True)

	for name in UNUSED_WORK_CENTERS:
		if frappe.db.exists("Production Work Center", name):
			frappe.delete_doc("Production Work Center", name, force=True, ignore_permissions=True)

