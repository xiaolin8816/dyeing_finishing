import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate
from dyeing_finishing.dyeing_finishing.doctype.color_master.color_master import (
    get_grey_fabric_batch_details,
)


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
        self.customer_name = self.customer
        self.finished_product_name = color_master.product_name
        if not self.grey_fabric_batch:
            self.grey_fabric_batch = color_master.grey_fabric_batch
        if not self.grey_fabric and not self.grey_fabric_batch:
            self.grey_fabric = color_master.grey_fabric

    def _set_grey_fabric_details(self):
        if self.grey_fabric_batch:
            detail = get_grey_fabric_batch_details(
                self.grey_fabric_batch, customer=self.customer
            )
            self.grey_fabric = detail.grey_fabric
            self.grey_fabric_code = detail.grey_fabric_code
            self.grey_fabric_name = detail.grey_fabric_name
            return

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
