from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields({
		"Stock Entry": [{"fieldname":"custom_finished_product_to_grey_fabric","label":"成品库存转胚布仓","fieldtype":"Link","options":"Finished Product to Grey Fabric","insert_after":"custom_finished_product_return_to_grey_fabric","read_only":1,"no_copy":1}],
		"Stock Entry Detail": [{"fieldname":"custom_finished_product_to_grey_fabric","label":"成品库存转胚布仓","fieldtype":"Link","options":"Finished Product to Grey Fabric","insert_after":"custom_finished_product_return_to_grey_fabric","read_only":1,"no_copy":1}],
	}, update=True)
