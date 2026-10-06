import frappe


CUSTOMER_SERIES = "A.####"
CUSTOMER_SERIES_KEY = "A"


def execute():
	"""客户统一使用 A0001 格式自动编号。"""
	settings = frappe.get_single("Selling Settings")
	if settings.cust_master_name != "Naming Series":
		settings.cust_master_name = "Naming Series"
		settings.save(ignore_permissions=True)

	# 现有客户仅调整单据编号，customer_name 仍保留真实客户名称。
	if frappe.db.exists("Customer", "陈强") and not frappe.db.exists("Customer", "A0001"):
		frappe.rename_doc("Customer", "陈强", "A0001", force=True)

	# 重命名不会自动推进流水号，确保下一个新客户从 A0002 开始。
	frappe.db.sql(
		"""
		INSERT INTO `tabSeries` (`name`, `current`)
		VALUES (%s, 1)
		ON DUPLICATE KEY UPDATE `current` = GREATEST(`current`, 1)
		""",
		CUSTOMER_SERIES_KEY,
	)

	frappe.clear_cache(doctype="Customer")
