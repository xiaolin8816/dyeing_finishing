from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields({
		"Stock Entry": [{"fieldname":"custom_customer_grey_fabric_return","label":"客户胚布退货单号","fieldtype":"Data","insert_after":"custom_grey_fabric_customer_transfer","read_only":1,"no_copy":1}],
		"Stock Entry Detail": [{"fieldname":"custom_customer_grey_fabric_return","label":"客户胚布退货单号","fieldtype":"Data","insert_after":"custom_grey_fabric_customer_transfer","read_only":1,"no_copy":1}],
	}, update=True)
