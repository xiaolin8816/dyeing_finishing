function lock_confirmed_recipe(frm) {
 if (!frm._recipe_field_read_only) {
  frm._recipe_field_read_only = {};
  frm.fields.forEach(field => {
   frm._recipe_field_read_only[field.df.fieldname] = field.df.read_only;
  });
 }
 frm.fields.forEach(field => {
  frm.set_df_property(field.df.fieldname, "read_only", 1);
 });
 frm.disable_save();
}

function unlock_recipe(frm) {
 if (frm._recipe_field_read_only) {
  frm.fields.forEach(field => {
   const readOnly = frm._recipe_field_read_only[field.df.fieldname];
   frm.set_df_property(field.df.fieldname, "read_only", readOnly || 0);
  });
  delete frm._recipe_field_read_only;
 }
 frm.enable_save();
}

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
 refresh(frm) {
  if (frm.is_new()) return;

  if (frm.doc.recipe_status === "已确认") {
   frm.add_custom_button("取消确认", () => {
    frappe.confirm("取消确认后，配方将恢复为草稿。是否继续？", () => {
     frappe.call({
      method: "dyeing_finishing.dyeing_finishing.doctype.laboratory_recipe.laboratory_recipe.cancel_recipe_confirmation",
      args: {name: frm.doc.name},
      freeze: true,
      freeze_message: "正在取消确认…",
      callback: () => frm.reload_doc()
     });
    });
   }, "操作");
   lock_confirmed_recipe(frm);
  } else {
   unlock_recipe(frm);
  }

  if (frm.doc.recipe_status !== "已确认" && frm.doc.recipe_status !== "停用") {
   frm.add_custom_button("确认配方", () => {
    frappe.confirm("确认后将作为该色号的当前化验配方。是否继续？", () => {
     frappe.call({
      method: "dyeing_finishing.dyeing_finishing.doctype.laboratory_recipe.laboratory_recipe.confirm_recipe",
      args: {name: frm.doc.name},
      freeze: true,
      freeze_message: "正在确认配方…",
      callback: () => frm.reload_doc()
     });
    });
   }, "操作");
  }
 },
 color_no(frm) {
  if (!frm.doc.color_no) return;
  frappe.db.get_doc("Color Master", frm.doc.color_no).then(color => {
   const customer = color.customer_name || "";
   frm.set_value("color", color.color_name || "");
   frm.set_value("customer", customer);
   if (customer) {
    frappe.db.get_value("Customer", customer, "customer_name").then(({message}) => {
     frm.set_value("customer_name", message?.customer_name || customer);
    });
   } else {
    frm.set_value("customer_name", "");
   }
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
