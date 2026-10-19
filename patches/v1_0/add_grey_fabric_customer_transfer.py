from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields({
		"Stock Entry": [{"fieldname":"custom_grey_fabric_customer_transfer","label":"胚布过户单","fieldtype":"Link","options":"Grey Fabric Customer Transfer","insert_after":"custom_finished_product_customer_transfer","read_only":1,"no_copy":1}],
		"Stock Entry Detail": [{"fieldname":"custom_grey_fabric_customer_transfer","label":"胚布过户单","fieldtype":"Link","options":"Grey Fabric Customer Transfer","insert_after":"custom_finished_product_customer_transfer","read_only":1,"no_copy":1}],
	}, update=True)
