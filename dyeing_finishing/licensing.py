"""Time-based product declaration consumed by the reusable License Core APP."""

from dyeing_finishing import __version__


def get_license_product():
	return {
		"product_id": "dyeing_finishing",
		"product_name": "印染行业 ERP",
		"app_name": "dyeing_finishing",
		"app_version": __version__,
		"trial_days": 30,
	}
