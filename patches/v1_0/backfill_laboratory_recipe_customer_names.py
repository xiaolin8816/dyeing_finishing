import frappe


def execute():
	"""化验室配方保留客户编号关联，客户名称字段改为显示真实名称。"""
	for recipe in frappe.get_all(
		"Laboratory Recipe", fields=["name", "customer", "customer_name"]
	):
		customer = recipe.customer or recipe.customer_name
		if not customer or not frappe.db.exists("Customer", customer):
			continue
		frappe.db.set_value(
			"Laboratory Recipe",
			recipe.name,
			{
				"customer": customer,
				"customer_name": frappe.db.get_value(
					"Customer", customer, "customer_name"
				)
				or customer,
			},
			update_modified=False,
		)
