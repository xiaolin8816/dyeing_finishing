import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import cint
class GreyFabricMaster(Document):
 def autoname(self):
  self.name=make_autoname("PB.#####")
  self.item_code=self.name
 def validate(self):
  self.item_code=self.name
  if not frappe.db.exists("Item Group","胚布"): frappe.throw(_("未找到“胚布”物料组，请先建立该物料组"))
  if self.default_warehouse:
   warehouse=frappe.db.get_value("Warehouse",self.default_warehouse,["is_group","disabled"],as_dict=True)
   if not warehouse or warehouse.is_group or warehouse.disabled: frappe.throw(_("默认货位必须是启用的末级仓库"))
 def after_insert(self): self.sync_item()
 def on_update(self): self.sync_item()
 def sync_item(self):
  values={"item_code":self.item_code,"item_name":self.fabric_name,"item_group":"胚布","stock_uom":self.stock_uom,"has_batch_no":cint(self.has_batch_no),"disabled":0 if cint(self.enabled) else 1}
  if frappe.db.exists("Item",self.item_code):
   item=frappe.get_doc("Item",self.item_code); item.update(values); item.save(ignore_permissions=True)
  else: frappe.get_doc({"doctype":"Item",**values}).insert(ignore_permissions=True)