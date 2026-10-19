import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate, nowdate
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
        self._prevent_confirmed_recipe_changes()
        self.recipe_no = self.name
        self.sampling_date = self.sampling_date or getdate(nowdate())
        self.recipe_version = self.recipe_version or "V1"
        self._set_color_details()
        self._set_grey_fabric_details()
        self._validate_process_parameter_template()
        if self.recipe_status == "已确认":
            self.confirmation_date = self.confirmation_date or getdate(nowdate())
            frappe.db.set_value("Color Master", self.color_no, "lab_record", self.name, update_modified=False)

    def _prevent_confirmed_recipe_changes(self):
        if self.is_new():
            return

        previous_status = frappe.db.get_value("Laboratory Recipe", self.name, "recipe_status")
        if previous_status == "已确认" and not self.flags.allow_cancel_recipe_confirmation:
            frappe.throw(_("已确认的配方不能修改，请先取消确认"))
        if (
            previous_status != "已确认"
            and self.recipe_status == "已确认"
            and not self.flags.allow_recipe_confirmation
        ):
            frappe.throw(_("请使用“确认配方”操作确认配方"))

    def _set_color_details(self):
        if not self.color_no:
            frappe.throw(_("请选择色号"))
        existing_recipe = frappe.db.get_value(
            "Laboratory Recipe",
            {"color_no": self.color_no, "name": ["!=", self.name or ""]},
            "name",
        )
        if existing_recipe:
            frappe.throw(
                _("\u8272\u53f7 {0} \u5df2\u5efa\u7acb\u5316\u9a8c\u5ba4\u914d\u65b9\uff1a{1}\uff0c\u4e0d\u80fd\u91cd\u590d\u5efa\u6863").format(
                    self.color_no, existing_recipe
                )
            )
        color_master = frappe.get_doc("Color Master", self.color_no)
        if color_master.status != "启用":
            frappe.throw(_("只能选择状态为启用的色号"))
        self.color = color_master.color_name
        self.customer = color_master.customer_name
        self.customer_name = (
            frappe.db.get_value("Customer", self.customer, "customer_name")
            or self.customer
        )
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


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_available_color_numbers(doctype, txt, searchfield, start, page_len, filters=None):
    """只返回启用且尚未建立化验室配方的色号。"""
    filters = frappe.parse_json(filters) or {}
    current_recipe = filters.get("current_recipe") or ""
    return frappe.db.sql(
        """
        SELECT color.name, color.color_name, color.product_name
        FROM `tabColor Master` color
        WHERE color.status = '启用'
          AND (
              color.name LIKE %(txt)s
              OR COALESCE(color.color_name, '') LIKE %(txt)s
              OR COALESCE(color.product_name, '') LIKE %(txt)s
          )
          AND NOT EXISTS (
              SELECT 1
              FROM `tabLaboratory Recipe` recipe
              WHERE recipe.color_no = color.name
                AND recipe.name != %(current_recipe)s
          )
        ORDER BY color.modified DESC, color.name
        LIMIT %(page_len)s OFFSET %(start)s
        """,
        {
            "txt": f"%{txt}%",
            "current_recipe": current_recipe,
            "page_len": cint(page_len),
            "start": cint(start),
        },
    )


def _get_recipe_for_confirmation(name):
    recipe = frappe.get_doc("Laboratory Recipe", name)
    if not frappe.has_permission("Laboratory Recipe", "write", recipe):
        frappe.throw(_("无权确认化验室配方"))
    return recipe


@frappe.whitelist()
def confirm_recipe(name):
    recipe = _get_recipe_for_confirmation(name)
    if recipe.recipe_status == "停用":
        frappe.throw(_("停用的配方不能确认"))

    recipe.recipe_status = "已确认"
    recipe.confirmation_date = getdate(nowdate())
    recipe.flags.allow_recipe_confirmation = True
    recipe.save()
    return recipe.name


@frappe.whitelist()
def cancel_recipe_confirmation(name):
    recipe = _get_recipe_for_confirmation(name)
    if recipe.recipe_status != "已确认":
        frappe.throw(_("只有已确认的配方才能取消确认"))

    recipe.recipe_status = "草稿"
    recipe.confirmation_date = None
    recipe.flags.allow_cancel_recipe_confirmation = True
    recipe.save()

    if frappe.db.get_value("Color Master", recipe.color_no, "lab_record") == recipe.name:
        frappe.db.set_value("Color Master", recipe.color_no, "lab_record", None, update_modified=False)
    return recipe.name
