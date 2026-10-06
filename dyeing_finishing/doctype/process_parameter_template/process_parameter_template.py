import frappe
from frappe import _
from frappe.model.document import Document


class ProcessParameterTemplate(Document):
    def before_insert(self):
        self.template_no = self.name

    def validate(self):
        self.template_no = self.name


@frappe.whitelist()
def get_process_parameter_template_items(template_name):
    template = frappe.get_doc("Process Parameter Template", template_name)
    if template.status != "启用":
        frappe.throw(_("只能引用状态为启用的工艺参数模板"))
    return {
        "process_type": template.process_type,
        "items": [
        {
            "process_stage": row.process_stage,
            "parameter_name": row.parameter_name,
            "unit": row.unit,
            "default_value": row.default_value,
            "parameter_value": row.default_value,
            "instruction": row.instruction,
        }
        for row in template.parameter_items
        ],
    }
