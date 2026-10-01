import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


class LaboratoryRecipe(Document):
    def before_insert(self):
        self.recipe_no = self.name
        self.sampling_date = self.sampling_date or getdate(nowdate())
        self.recipe_version = self.recipe_version or "V1"
        self.recipe_status = self.recipe_status or "草稿"

    def validate(self):
        self.recipe_no = self.name
        self.sampling_date = self.sampling_date or getdate(nowdate())
        self.recipe_version = self.recipe_version or "V1"
        self._set_color_details()
        self._set_grey_fabric_details()
        self._validate_process_parameter_template()
        if self.recipe_status == "已确认":
            self.confirmation_date = self.confirmation_date or getdate(nowdate())
            frappe.db.set_value("Color Master", self.color_no, "lab_record", self.name, update_modified=False)

    def _set_color_details(self):
        if not self.color_no:
            frappe.throw(_("请选择色号"))
        color_master = frappe.get_doc("Color Master", self.color_no)
        if color_master.status != "启用":
            frappe.throw(_("只能选择状态为启用的色号"))
        self.color = color_master.color_name
        self.customer = color_master.customer_name
        self.customer_name = frappe.db.get_value("Customer", self.customer, "customer_name") or self.customer
        self.finished_product_name = color_master.product_name
        if not self.grey_fabric:
            self.grey_fabric = color_master.grey_fabric

    def _set_grey_fabric_details(self):
        if not self.grey_fabric:
            self.grey_fabric_code = None
            self.grey_fabric_name = None
            return
        fabric = frappe.get_doc("Grey Fabric Master", self.grey_fabric)
        self.grey_fabric_code = fabric.item_code
        self.grey_fabric_name = fabric.fabric_name

    def _validate_process_parameter_template(self):
        if not self.process_parameter_template:
            return
        template = frappe.get_doc("Process Parameter Template", self.process_parameter_template)
        if template.status != "启用":
            frappe.throw(_("只能选择状态为启用的工艺参数模板"))
        if not self.process_type:
            self.process_type = template.process_type
        elif self.process_type != template.process_type:
            frappe.throw(_("加工类型必须与工艺参数模板的加工类型一致"))
