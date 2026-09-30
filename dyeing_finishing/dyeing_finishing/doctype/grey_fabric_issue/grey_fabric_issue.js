frappe.ui.form.on("Grey Fabric Issue", {
 setup(frm) {
  frm.set_query("flow_card", () => ({filters:{docstatus:["!=",2]}}));
  frm.set_query("batch_no", "items", (doc, cdt, cdn) => {const row=locals[cdt][cdn];return {query:"dyeing_finishing.dyeing_finishing.doctype.grey_fabric_issue.grey_fabric_issue.get_available_grey_fabric_batches",filters:{flow_card:frm.doc.flow_card,source_row:row.flow_card_grey_fabric_issue}};});
 },
 refresh(frm) {if (frm.is_new() || frm.doc.docstatus===0) frm.add_custom_button("新增补充批次",()=>addSupplement(frm),"胚布出库");},
 flow_card(frm) {
  if (!frm.doc.flow_card) {frm.clear_table("items");frm.refresh_field("items");return;}
  frappe.call({method:"dyeing_finishing.dyeing_finishing.doctype.grey_fabric_issue.grey_fabric_issue.get_grey_fabric_issue_flow_card_details",args:{flow_card:frm.doc.flow_card},freeze:true,freeze_message:"正在带出流转卡胚布资料…",callback:({message})=>{
   if(!message)return;["sales_order","customer","customer_name","color_no","color","finished_product_name","finished_specification"].forEach(f=>frm.set_value(f,message[f]||""));frm._greyFabricPlans=message.plan_rows||[];frm.clear_table("items");(message.items||[]).forEach(data=>{const row=frm.add_child("items");Object.keys(data).forEach(f=>frappe.model.set_value(row.doctype,row.name,f,data[f]));});frm.refresh_field("items");setTotals(frm);
  }});
 }
});
frappe.ui.form.on("Grey Fabric Issue Item", {
 batch_no(frm,cdt,cdn) {const row=locals[cdt][cdn];if(!row.batch_no)return;frappe.call({method:"dyeing_finishing.dyeing_finishing.doctype.grey_fabric_issue.grey_fabric_issue.get_grey_fabric_issue_batch_details",args:{batch_no:row.batch_no,customer:frm.doc.customer,location:row.location||null},callback:({message})=>{if(!message)return;["item_code","grey_fabric_name","specification","color","stock_roll_count","stock_qty","warehouse","location"].forEach(f=>frappe.model.set_value(cdt,cdn,f,message[f]||""));setShortage(cdt,cdn);}});},
 issue_roll_count(frm,cdt,cdn){setShortage(cdt,cdn);setTotals(frm);},
 issue_qty(frm,cdt,cdn){setShortage(cdt,cdn);setTotals(frm);},
 items_remove(frm){setTotals(frm);}
});
function addSupplement(frm) {const plans=frm._greyFabricPlans||[];if(!frm.doc.flow_card||!plans.length){frappe.msgprint("请先选择包含胚布领用计划的生产流转卡。");return;}const options=plans.map(p=>`${p.name}｜${p.grey_fabric_name||"未填写胚布"}｜${p.color||"无颜色"}`);frappe.prompt([{fieldname:"plan",label:"胚布领用计划",fieldtype:"Select",options:options.join("\n"),reqd:1}],values=>{const p=plans[options.indexOf(values.plan)],row=frm.add_child("items");["grey_fabric_name","color","planned_roll_count","planned_qty","warehouse","location"].forEach(f=>frappe.model.set_value(row.doctype,row.name,f,p[f]||""));frappe.model.set_value(row.doctype,row.name,"flow_card_grey_fabric_issue",p.name);frappe.model.set_value(row.doctype,row.name,"source_type","补充批次");frm.refresh_field("items");},"新增补充批次","确定");}
function setTotals(frm){const rows=frm.doc.items||[];frm.set_value("issue_roll_count",rows.reduce((total,row)=>total+flt(row.issue_roll_count),0));frm.set_value("issue_qty",rows.reduce((total,row)=>total+flt(row.issue_qty),0));}
function setShortage(cdt,cdn){const row=locals[cdt][cdn];frappe.model.set_value(cdt,cdn,"shortage_roll_count",Math.max(flt(row.planned_roll_count)-flt(row.issued_roll_count)-flt(row.issue_roll_count),0));frappe.model.set_value(cdt,cdn,"shortage_qty",Math.max(flt(row.planned_qty)-flt(row.issued_qty)-flt(row.issue_qty),0));}
