import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields({
		"Stock Entry": [{"fieldname":"custom_finished_product_return_to_grey_fabric","label":"成品退货转胚布仓","fieldtype":"Link","options":"Finished Product Return to Grey Fabric","insert_after":"custom_finished_product_return","read_only":1,"no_copy":1}],
		"Stock Entry Detail": [{"fieldname":"custom_finished_product_return_to_grey_fabric","label":"成品退货转胚布仓","fieldtype":"Link","options":"Finished Product Return to Grey Fabric","insert_after":"custom_finished_product_return","read_only":1,"no_copy":1}],
	}, update=True)
	if frappe.db.exists("DocType", "Dyeing System Settings"):
		frappe.db.set_single_value("Dyeing System Settings", "return_rework_warehouse", "返修待处理仓 - 沅泰")
