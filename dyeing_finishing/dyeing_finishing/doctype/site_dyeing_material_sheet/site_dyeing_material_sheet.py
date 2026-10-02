import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt, getdate, nowdate

class SiteDyeingMaterialSheet(Document):
 def autoname(self): self.name = make_autoname("RL.YY.MM.DD.###")
 def before_insert(self):
  self.material_sheet_no=self.name; self.material_sheet_status=self.material_sheet_status or "保存"; self.planned_dyeing_date=self.planned_dyeing_date or getdate(nowdate())
 def validate(self):
  self.material_sheet_no=self.name; self.planned_dyeing_date=self.planned_dyeing_date or getdate(nowdate()); self._set_card(); self._set_issue(); self._set_recipe(); self._calculate()
 def _set_card(self):
  if not self.production_flow_card: frappe.throw(_("请选择生产流转卡"))
  card=frappe.get_doc("Production Flow Card",self.production_flow_card)
  if card.docstatus==2: frappe.throw(_("不能引用已取消的生产流转卡"))
  self.sales_order=card.sales_order; self.customer=card.customer; self.customer_name=frappe.db.get_value("Customer",card.customer,"customer_name") or card.customer; self.color_no=card.color_no; self.color=card.color; self.finished_product_name=card.finished_product_name; self.production_qty=card.production_qty
 def _set_issue(self):
  self.grey_fabric_issue=self.grey_fabric_issue or _latest_issue(self.production_flow_card)
  if not self.grey_fabric_issue: frappe.throw(_("当前生产流转卡没有已提交的胚布出库单，不能生成现场染色料单"))
  issue=frappe.get_doc("Grey Fabric Issue",self.grey_fabric_issue)
  if issue.docstatus!=1 or issue.flow_card!=self.production_flow_card: frappe.throw(_("胚布出库单必须已提交且属于当前生产流转卡"))
  row=next((x for x in issue.items if x.batch_no==self.grey_fabric_batch),None) or (issue.items[0] if issue.items else None)
  if not row: frappe.throw(_("胚布出库单没有可用的胚布出库明细"))
  self.grey_fabric_batch=row.batch_no; self.grey_fabric_name=row.grey_fabric_name; self.grey_fabric_uom=frappe.db.get_value("Item",row.item_code,"stock_uom")
  maximum=flt(row.issue_qty)
  if not flt(self.grey_fabric_issue_qty): self.grey_fabric_issue_qty=maximum
  if flt(self.grey_fabric_issue_qty)<0 or flt(self.grey_fabric_issue_qty)>maximum: frappe.throw(_("胚布出库数量应在 0 至关联胚布出库单的本次出库数量 {0} 之间").format(maximum))
 def _set_recipe(self):
  if not self.laboratory_recipe: frappe.throw(_("请选择已确认的化验室配方"))
  recipe=frappe.get_doc("Laboratory Recipe",self.laboratory_recipe)
  if recipe.recipe_status!="已确认" or recipe.color_no!=self.color_no: frappe.throw(_("只能选择当前色号已确认的化验室配方"))
  self.recipe_version=recipe.recipe_version; self.bath_ratio=self.bath_ratio or recipe.bath_ratio
  if self.recipe_snapshot_source!=recipe.name or not self.items or (recipe.process_parameters and not self.process_parameters): self._copy_recipe(recipe)
 def _copy_recipe(self,recipe):
  self.set("items",[])
  for s in recipe.get("recipe_items") or []: self.append("items",{"item_code":s.item_code,"item_name":s.item_name,"material_category":s.material_category,"uom":s.uom,"dosage_basis":s.dosage_basis,"formula_qty":s.formula_qty,"site_ratio":s.formula_qty,"temporary_qty":0,"issue_status":"未领料","remark":s.remark})
  self.set("process_parameters",[])
  for s in recipe.get("process_parameters") or []:
   value=s.parameter_value or s.default_value; self.append("process_parameters",{"process_stage":s.process_stage,"parameter_name":s.parameter_name,"unit":s.unit,"parameter_value":value,"site_parameter_value":value,"instruction":s.instruction})
  self.recipe_snapshot_source=recipe.name
 def _calculate(self):
  base,bath=flt(self.grey_fabric_issue_qty),flt(self.bath_volume)
  for r in self.items:
   ratio,temp=flt(r.site_ratio),flt(r.temporary_qty)
   actual=base*ratio*10+temp if r.dosage_basis=="g/kg" else base*ratio/100+temp if r.dosage_basis=="%owf" else bath*ratio+temp if r.dosage_basis=="g/L" else ratio+temp
   if actual<0: frappe.throw(_("第 {0} 行实际用量不能小于 0").format(r.idx))
   r.actual_qty=actual

def _latest_issue(flow_card): return frappe.db.get_value("Grey Fabric Issue",{"flow_card":flow_card,"docstatus":1},"name",order_by="outbound_date desc, modified desc")
@frappe.whitelist()
def get_site_dyeing_material_sheet_flow_card_details(flow_card):
 card=frappe.get_doc("Production Flow Card",flow_card)
 if card.docstatus==2: frappe.throw(_("不能引用已取消的生产流转卡"))
 issue=_latest_issue(flow_card); r={"sales_order":card.sales_order,"customer":card.customer,"customer_name":frappe.db.get_value("Customer",card.customer,"customer_name") or card.customer,"color_no":card.color_no,"color":card.color,"finished_product_name":card.finished_product_name,"production_qty":card.production_qty,"grey_fabric_issue":issue or "","grey_fabric_batch":"","grey_fabric_name":"","grey_fabric_issue_qty":0,"grey_fabric_uom":""}
 if issue:
  x=(frappe.get_doc("Grey Fabric Issue",issue).items or [None])[0]
  if x: r.update({"grey_fabric_batch":x.batch_no,"grey_fabric_name":x.grey_fabric_name,"grey_fabric_issue_qty":x.issue_qty,"grey_fabric_uom":frappe.db.get_value("Item",x.item_code,"stock_uom") or ""})
 return r
