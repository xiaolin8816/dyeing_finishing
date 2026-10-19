import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class DyeingPaperFormat(Document):
	def validate(self):
		self.paper_name = (self.paper_name or "").strip()
		if not self.paper_name:
			frappe.throw(_("纸张格式名称不能为空"))
		for fieldname in ("width_mm", "height_mm"):
			value = flt(self.get(fieldname))
			if value <= 0 or value > 1000:
				frappe.throw(_("纸张宽度和高度必须在 0–1000 mm 之间"))
		for fieldname in ("margin_top_mm", "margin_bottom_mm", "margin_left_mm", "margin_right_mm", "label_gap_mm"):
			if flt(self.get(fieldname)) < 0:
				frappe.throw(_("边距和标签间隔不能为负数"))
		self.orientation = "横向" if flt(self.width_mm) > flt(self.height_mm) else "纵向"

