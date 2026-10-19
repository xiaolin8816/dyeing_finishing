import frappe


DEFAULTS = {
	"production_transit_warehouse": "生产中转仓 - 沅泰",
	"dye_material_warehouse": "染料仓库 - 沅泰",
	"finished_product_warehouse": "成品仓库 - 沅泰",
	"finished_product_return_warehouse": "成品退货待检仓 - 沅泰",
	"return_rework_warehouse": "返修待处理仓 - 沅泰",
	"weight_uom": "Kg",
	"yard_uom": "Y",
	"grey_fabric_item_group": "胚布",
	"dye_item_group": "染料",
	"auxiliary_item_group": "助剂",
	"finished_product_item_group": "成品",
	"allow_partial_packing": 1,
	"allow_partial_delivery": 1,
	"packing_weight_tolerance_percent": 5,
	"license_reminder_days": 30,
}


def get_setting(fieldname):
	if not frappe.db.exists("DocType", "Dyeing System Settings"):
		return DEFAULTS.get(fieldname)
	if not _has_saved_value(fieldname):
		return DEFAULTS.get(fieldname)
	value = frappe.db.get_single_value("Dyeing System Settings", fieldname)
	return DEFAULTS.get(fieldname) if value in (None, "") else value


def _has_saved_value(fieldname):
	return bool(frappe.db.sql(
		"SELECT 1 FROM `tabSingles` WHERE doctype=%s AND field=%s LIMIT 1",
		("Dyeing System Settings", fieldname),
	))


def get_dye_material_groups():
	return tuple(dict.fromkeys((get_setting("dye_item_group"), get_setting("auxiliary_item_group"))))


@frappe.whitelist()
def get_dyeing_system_defaults():
	return {fieldname: get_setting(fieldname) for fieldname in DEFAULTS}


def add_dyeing_settings_to_boot(bootinfo):
	bootinfo.dyeing_system_settings = get_dyeing_system_defaults()


def initialize_dyeing_system_settings():
	if not frappe.db.exists("DocType", "Dyeing System Settings"):
		return
	values = {fieldname: value for fieldname, value in DEFAULTS.items() if not _has_saved_value(fieldname)}
	for fieldname, value in values.items():
		frappe.db.set_single_value("Dyeing System Settings", fieldname, value)
