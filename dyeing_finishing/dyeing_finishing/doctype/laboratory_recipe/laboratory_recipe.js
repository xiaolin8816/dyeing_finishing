frappe.ui.form.on("Laboratory Recipe", {
 setup(frm) {
  frm.set_query("color_no", () => ({filters:{status:"启用"}}));
  frm.set_query("process_parameter_template", () => ({filters:{status:"启用"}}));
  frm.set_query("grey_fabric_batch", () => ({
   query: "dyeing_finishing.dyeing_finishing.doctype.color_master.color_master.get_grey_fabric_batches",
   filters: {customer: frm.doc.customer}
  }));
  frm.set_query("item_code", "recipe_items", () => ({
   filters: {
    item_group: ["in", ["染料", "助剂"]],
    disabled: 0
   }
  }));
 },
 color_no(frm) {
  if (!frm.doc.color_no) return;
  frappe.db.get_doc("Color Master", frm.doc.color_no).then(color => {
   frm.set_value("color", color.color_name || "");
   frm.set_value("customer", color.customer_name || "");
   frm.set_value("finished_product_name", color.product_name || "");
   frm.set_value("grey_fabric_batch", color.grey_fabric_batch || "");
   if (!color.grey_fabric_batch) {
    frm.set_value("grey_fabric", color.grey_fabric || "");
    frm.set_value("grey_fabric_code", color.grey_fabric_code || "");
    frm.set_value("grey_fabric_name", color.grey_fabric_name || "");
   }
  });
 },
 grey_fabric_batch(frm) {
  if (!frm.doc.grey_fabric_batch) {
   frm.set_value("grey_fabric", "");
   frm.set_value("grey_fabric_code", "");
   frm.set_value("grey_fabric_name", "");
   return;
  }
  frappe.call({
   method: "dyeing_finishing.dyeing_finishing.doctype.color_master.color_master.get_grey_fabric_batch_details",
   args: {
    batch_no: frm.doc.grey_fabric_batch,
    customer: frm.doc.customer
   },
   callback: ({message}) => {
    if (!message) return;
    frm.set_value("grey_fabric", message.grey_fabric || "");
    frm.set_value("grey_fabric_code", message.grey_fabric_code || "");
    frm.set_value("grey_fabric_name", message.grey_fabric_name || "");
   }
  });
 },
 process_parameter_template(frm) {
  if (!frm.doc.process_parameter_template) return;
  frappe.call({
   method: "dyeing_finishing.dyeing_finishing.doctype.process_parameter_template.process_parameter_template.get_process_parameter_template_items",
   args: {template_name: frm.doc.process_parameter_template},
   freeze: true,
   freeze_message: "正在带入工艺参数项目…",
   callback: ({message}) => {
    if (!message) return;
    frm.clear_table("process_parameters");
    (message.items || []).forEach(data => {
     const row = frm.add_child("process_parameters");
     Object.keys(data).forEach(key => frappe.model.set_value(row.doctype, row.name, key, data[key] || ""));
    });
    frm.refresh_field("process_parameters");
   }
  });
 }
});
