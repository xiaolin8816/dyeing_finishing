import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt, getdate, nowdate
from dyeing_finishing.dyeing_finishing.doctype.production_flow_card.production_flow_card import record_production_progress

ALLOWED_ITEM_GROUPS = ("染料", "助剂")
MANUAL_SOURCE = "手动新增"
RECIPE_SOURCE = "配方带出"
MANUAL_ITEM_FIELDS = ("item_code", "item_name", "material_category", "uom", "dosage_basis", "formula_qty", "site_ratio", "temporary_qty", "actual_qty", "issued_qty", "issue_status", "remark", "source")

class SiteDyeingMaterialSheet(Document):
 def autoname(self): self.name = make_autoname("RL.YY.MM.DD.###")
 def before_validate(self):
  if self.is_new() and self.material_sheet_type in ("追加染色", "返修染色") and self.previous_material_sheet:
   self._initialize_followup()
 def before_insert(self):
  self.material_sheet_no=self.name; self.material_sheet_status=self.material_sheet_status or "保存"; self.planned_dyeing_date=self.planned_dyeing_date or getdate(nowdate())
 def validate(self):
  self.material_sheet_no=self.name; self.planned_dyeing_date=self.planned_dyeing_date or getdate(nowdate()); self._set_card(); self._set_issue(); self._validate_followup_items(); self._set_recipe(); self._validate_manual_items(); self._calculate()
 def _initialize_followup(self):
  source=frappe.get_doc("Site Dyeing Material Sheet",self.previous_material_sheet)
  if source.docstatus!=1:
   frappe.throw(_("只能从已提交的现场染色料单创建追加或返修料单"))
  if source.material_sheet_status=="已取消":
   frappe.throw(_("不能从已取消的现场染色料单创建后续料单"))
  if self.material_sheet_type=="返修染色" and source.material_sheet_status!="已完成":
   frappe.throw(_("返修染色料单只能从已完成的现场染色料单创建"))
  if self.material_sheet_type=="返修染色" and not (self.rework_reason or "").strip():
   frappe.throw(_("请填写返修原因"))
  self.original_material_sheet=source.original_material_sheet or source.name
  self.production_flow_card=source.production_flow_card
  self.grey_fabric_issue=source.grey_fabric_issue
  self.grey_fabric_batch=source.grey_fabric_batch
  self.grey_fabric_issue_qty=source.grey_fabric_issue_qty
  self.dyeing_machine=self.dyeing_machine or source.dyeing_machine
  self.dyeing_sequence=frappe.db.count("Site Dyeing Material Sheet",{"production_flow_card":source.production_flow_card,"docstatus":["!=",2]})+1
  if not self.laboratory_recipe:
   self.laboratory_recipe=_get_default_confirmed_recipe(source.color_no) or ""
  if not self.items:
   self.recipe_snapshot_source=""
   self.recipe_version=""
   self.bath_ratio=""
   self.bath_volume=0
   self.set("process_parameters",[])
 def _validate_followup_items(self):
  if self.material_sheet_type not in ("追加染色", "返修染色"):
   return
  if not self.items or not any(row.item_code for row in self.items):
   frappe.throw(_("追加或返修染色料单必须保留至少一条现场料单明细，不能保存空明细料单"))
 def before_submit(self):
  if not self.items or not any(row.item_code for row in self.items):
   frappe.throw(_("现场料单明细不能为空，不能提交"))
  self.material_sheet_status="待领料"
 def on_submit(self):
  record_production_progress(
   self.production_flow_card, "染色", "待领料", "Site Dyeing Material Sheet", self.name,
   batch_no=self.grey_fabric_batch, quantity=self.grey_fabric_issue_qty, uom=self.grey_fabric_uom,
   dyeing_machine=self.dyeing_machine, material_sheet_type=self.material_sheet_type,
   dyeing_sequence=self.dyeing_sequence, description="现场染色料单已提交",
  )
 def on_cancel(self):
  has_issued_qty=any(flt(row.issued_qty)>0 for row in self.items)
  if has_issued_qty or self.material_sheet_status in ("部分领料","已领料","已完成"):
   frappe.throw(_("料单已经发生领料或已完成，不能取消。请使用追加、返修或退料流程处理"))
  # 未领料的料单取消后恢复草稿，允许在原单修正并重新提交，无需建立修订单。
  self.db_set({"material_sheet_status":"保存","docstatus":0},update_modified=False)
  quote=chr(96)
  for table in ("tabSite Dyeing Material Sheet Item","tabSite Dyeing Material Sheet Process Parameter"):
   frappe.db.sql(f"UPDATE {quote}{table}{quote} SET docstatus=0 WHERE parent=%s AND parenttype='Site Dyeing Material Sheet'",self.name)
  self.material_sheet_status="保存"
  self.docstatus=0
  for row in self.items: row.docstatus=0
  for row in self.process_parameters: row.docstatus=0
  record_production_progress(
   self.production_flow_card, "染色", "染色料单已撤销", "Site Dyeing Material Sheet", self.name,
   batch_no=self.grey_fabric_batch, quantity=self.grey_fabric_issue_qty, uom=self.grey_fabric_uom,
   dyeing_machine=self.dyeing_machine, material_sheet_type=self.material_sheet_type,
   dyeing_sequence=self.dyeing_sequence, description="未发生领料，料单已恢复草稿",
  )
  self.add_comment("Edit",_("未发生领料，料单已恢复为草稿，可修改后重新提交。"))
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
  if not self.items or (recipe.process_parameters and not self.process_parameters):
   self._copy_recipe(recipe)
  else:
   self.recipe_snapshot_source=self.recipe_snapshot_source or recipe.name
 def _copy_recipe(self,recipe):
  manual_items=[{field: row.get(field) for field in MANUAL_ITEM_FIELDS} for row in self.items if row.source==MANUAL_SOURCE and row.item_code]
  self.set("items",[])
  for s in recipe.get("recipe_items") or []: self.append("items",{"source":RECIPE_SOURCE,"item_code":s.item_code,"item_name":s.item_name,"material_category":s.material_category,"uom":s.uom,"dosage_basis":s.dosage_basis,"formula_qty":s.formula_qty,"site_ratio":s.formula_qty,"temporary_qty":0,"issue_status":"未领料","remark":s.remark})
  for row in manual_items: self.append("items",row)
  self.set("process_parameters",[])
  for s in recipe.get("process_parameters") or []:
   value=s.parameter_value or s.default_value; self.append("process_parameters",{"process_stage":s.process_stage,"parameter_name":s.parameter_name,"unit":s.unit,"parameter_value":value,"site_parameter_value":value,"instruction":s.instruction})
  self.recipe_snapshot_source=recipe.name
 def _validate_manual_items(self):
  for row in self.items:
   row.source=row.source or RECIPE_SOURCE
   if row.source not in (RECIPE_SOURCE,MANUAL_SOURCE): frappe.throw(_("第 {0} 行来源无效").format(row.idx))
   if row.source!=MANUAL_SOURCE: continue
   item=frappe.db.get_value("Item",row.item_code,["item_name","item_group","stock_uom","disabled"],as_dict=True)
   if not item or item.disabled or item.item_group not in ALLOWED_ITEM_GROUPS:
    frappe.throw(_("第 {0} 行手动新增物料只能选择启用的染料或助剂").format(row.idx))
   row.item_name=item.item_name; row.material_category=item.item_group; row.uom=item.stock_uom; row.dosage_basis=row.dosage_basis or "g/kg"; row.formula_qty=flt(row.formula_qty)
 def _calculate(self):
  base,bath=flt(self.grey_fabric_issue_qty),flt(self.bath_volume)
  for r in self.items:
   ratio,temp=flt(r.site_ratio),flt(r.temporary_qty)
   actual=base*ratio*10+temp if r.dosage_basis=="g/kg" else base*ratio/100+temp if r.dosage_basis=="%owf" else bath*ratio+temp if r.dosage_basis=="g/L" else ratio+temp
   if actual<0: frappe.throw(_("第 {0} 行实际用量不能小于 0").format(r.idx))
   r.actual_qty=actual

def _latest_issue(flow_card): return frappe.db.get_value("Grey Fabric Issue",{"flow_card":flow_card,"docstatus":1},"name",order_by="outbound_date desc, modified desc")

def _get_default_confirmed_recipe(color_no):
 current = frappe.db.get_value("Color Master", color_no, "lab_record")
 if current and frappe.db.get_value("Laboratory Recipe", current, ["recipe_status", "color_no"], as_dict=True) == {"recipe_status": "已确认", "color_no": color_no}:
  return current
 return frappe.db.get_value("Laboratory Recipe", {"color_no": color_no, "recipe_status": "已确认"}, "name", order_by="confirmation_date desc, modified desc")

@frappe.whitelist()
def get_site_dyeing_material_sheet_flow_card_details(flow_card):
 card=frappe.get_doc("Production Flow Card",flow_card)
 if card.docstatus==2: frappe.throw(_("不能引用已取消的生产流转卡"))
 issue=_latest_issue(flow_card); r={"sales_order":card.sales_order,"customer":card.customer,"customer_name":frappe.db.get_value("Customer",card.customer,"customer_name") or card.customer,"color_no":card.color_no,"color":card.color,"finished_product_name":card.finished_product_name,"production_qty":card.production_qty,"grey_fabric_issue":issue or "","grey_fabric_batch":"","grey_fabric_name":"","grey_fabric_issue_qty":0,"grey_fabric_uom":"","laboratory_recipe":_get_default_confirmed_recipe(card.color_no) or ""}
 if issue:
  x=(frappe.get_doc("Grey Fabric Issue",issue).items or [None])[0]
  if x: r.update({"grey_fabric_batch":x.batch_no,"grey_fabric_name":x.grey_fabric_name,"grey_fabric_issue_qty":x.issue_qty,"grey_fabric_uom":frappe.db.get_value("Item",x.item_code,"stock_uom") or ""})
 return r



@frappe.whitelist()
def get_followup_material_sheet_defaults(source_name, sheet_type, rework_reason=None):
 if sheet_type not in ("追加染色", "返修染色"):
  frappe.throw(_("料单类型只能为追加染色或返修染色"))
 source=frappe.get_doc("Site Dyeing Material Sheet",source_name)
 source.check_permission("read")
 if source.docstatus!=1:
  frappe.throw(_("只能从已提交的现场染色料单创建追加或返修料单"))
 if source.material_sheet_status=="已取消":
  frappe.throw(_("不能从已取消的现场染色料单创建后续料单"))
 if sheet_type=="返修染色" and source.material_sheet_status!="已完成":
  frappe.throw(_("返修染色料单只能从已完成的现场染色料单创建"))
 if sheet_type=="返修染色" and not (rework_reason or "").strip():
  frappe.throw(_("请填写返修原因"))
 return {
  "material_sheet_type":sheet_type,
  "original_material_sheet":source.original_material_sheet or source.name,
  "previous_material_sheet":source.name,
  "rework_reason":(rework_reason or "").strip() if sheet_type=="返修染色" else "",
  "production_flow_card":source.production_flow_card,
  "sales_order":source.sales_order,
  "customer":source.customer,
  "customer_name":source.customer_name,
  "color_no":source.color_no,
  "color":source.color,
  "finished_product_name":source.finished_product_name,
  "production_qty":source.production_qty,
  "grey_fabric_issue":source.grey_fabric_issue,
  "grey_fabric_batch":source.grey_fabric_batch,
  "grey_fabric_name":source.grey_fabric_name,
  "grey_fabric_issue_qty":source.grey_fabric_issue_qty,
  "grey_fabric_uom":source.grey_fabric_uom,
  "dyeing_machine":source.dyeing_machine,
  "laboratory_recipe":_get_default_confirmed_recipe(source.color_no) or "",
  "recipe_snapshot_source":"",
  "recipe_version":"",
  "bath_ratio":"",
  "bath_volume":0
 }
