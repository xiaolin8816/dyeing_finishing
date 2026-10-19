const packingMethod = "dyeing_finishing.dyeing_finishing.doctype.finished_product_packing_receipt.finished_product_packing_receipt";

function calculatePackingTotals(frm) {
 const rows = frm.doc.items || [];
 const weight = rows.reduce((total, row) => total + flt(row.weight), 0);
 const grey = rows.reduce((total, row) => total + flt(row.grey_fabric_qty), 0);
 frm.set_value({
  total_roll_count: rows.length,
  total_weight: weight,
  total_yard_qty: rows.reduce((total, row) => total + flt(row.yard_qty), 0),
  total_grey_fabric_qty: grey,
  weight_difference: weight - grey,
  weight_difference_rate: grey ? (weight - grey) / grey * 100 : 0,
 });
}

function restorePackingBatches(frm) {
 frm.__packing_batches = (frm.doc.grey_fabric_batches || "")
  .split(/[；;]/)
  .map((batch) => batch.trim())
  .filter(Boolean);
}

function fillSinglePackingBatch(frm) {
 if ((frm.__packing_batches || []).length !== 1 || frm.doc.docstatus !== 0) return;
 const batch = frm.__packing_batches[0];
 (frm.doc.items || []).forEach((row) => {
  if (!row.grey_fabric_batch) frappe.model.set_value(row.doctype, row.name, "grey_fabric_batch", batch);
 });
}

frappe.ui.form.on("Finished Product Packing Receipt", {
 setup(frm) {
  frm.set_query("production_flow_card", () => ({filters: {docstatus: 1, production_status: ["!=", "已关闭"]}}));
  frm.set_query("grey_fabric_batch", "items", () => ({filters: {name: ["in", frm.__packing_batches || []]}}));
  const warehouse = frappe.boot.dyeing_system_settings?.finished_product_warehouse || "成品仓库 - 沅泰";
  frm.set_query("target_warehouse", () => ({filters: {name: warehouse, is_group: 0, disabled: 0}}));
 },

 refresh(frm) {
  restorePackingBatches(frm);
  fillSinglePackingBatch(frm);
 },

 production_flow_card(frm) {
  if (!frm.doc.production_flow_card) return;
  frappe.call({
   method: `${packingMethod}.get_packing_flow_card_details`,
   args: {flow_card: frm.doc.production_flow_card},
   freeze: true,
   freeze_message: "正在带出生产流转卡资料…",
   callback: ({message}) => {
    if (!message) return;
    ["sales_order", "sales_order_item", "customer", "customer_name", "color_no", "color",
     "finished_product_name", "finished_width", "finished_gsm", "finished_specification", "finished_uom",
     "order_qty", "process_type", "process_requirements", "packaging_requirements", "production_operations",
     "grey_fabric_issue_qty"].forEach((fieldname) => frm.set_value(fieldname, message[fieldname] || ""));
    frm.__packing_batches = message.grey_fabric_batches || [];
    frm.set_value("grey_fabric_batches", frm.__packing_batches.join("；"));
    frm.clear_table("items");
    frm.refresh_field("items");
    fillSinglePackingBatch(frm);
    if (!frm.__packing_batches.length) {
     frappe.msgprint("当前生产流转卡没有已提交的胚布出库批次，不能建立包装入库单。");
    }
   },
  });
 },

});

frappe.ui.form.on("Finished Product Packing Receipt Item", {
 items_add(frm, cdt, cdn) {
  frappe.model.set_value(cdt, cdn, "piece_no", (frm.doc.items || []).length);
  frappe.model.set_value(cdt, cdn, "weight_uom", "Kg");
  frappe.model.set_value(cdt, cdn, "yard_uom", "Y");
  frappe.model.set_value(cdt, cdn, "finished_grade", "一等品");
  frappe.model.set_value(cdt, cdn, "quality_flag", "合格");
  frappe.model.set_value(cdt, cdn, "packaging_method", "卷装");
  frappe.model.set_value(cdt, cdn, "warehouse_status", "未入库");
  if ((frm.__packing_batches || []).length === 1) {
   frappe.model.set_value(cdt, cdn, "grey_fabric_batch", frm.__packing_batches[0]);
  }
  calculatePackingTotals(frm);
 },
 items_remove: calculatePackingTotals,
 weight(frm, cdt, cdn) {
  const row = locals[cdt][cdn];
  if (!flt(row.grey_fabric_qty)) frappe.model.set_value(cdt, cdn, "grey_fabric_qty", flt(row.weight));
  calculatePackingTotals(frm);
 },
 grey_fabric_qty: calculatePackingTotals,
 yard_qty: calculatePackingTotals,
});
