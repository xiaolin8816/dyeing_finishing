import frappe
from frappe import _
from frappe.model.document import Document

from dyeing_finishing.license import decode_license, get_status


class DyeingFinishingLicense(Document):
	def before_save(self):
		frappe.only_for("System Manager")
		if self.license_file:
			file_doc = frappe.get_doc("File", {"file_url": self.license_file})
			content = file_doc.get_content()
			if isinstance(content, bytes):
				content = content.decode("utf-8")
			self.license_token = content.strip()
		if not self.license_token:
			frappe.throw(_("请上传许可证文件"))
		payload = decode_license(self.license_token)
		self.license_id = payload.license_id
		self.licensed_customer = payload.get("customer")
		self.licensed_site = payload.site
		self.valid_from = payload.valid_from
		self.expires_on = payload.expires_on

	def onload(self):
		self._apply_status()

	def on_update(self):
		self._apply_status()

	def _apply_status(self):
		status = get_status(update_clock=False)
		self.license_status = status.status
		self.remaining_days = status.remaining_days
		self.status_message = status.message
