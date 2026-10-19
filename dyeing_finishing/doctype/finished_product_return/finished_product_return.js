/* eslint-disable */
const RETURN_METHOD = "dyeing_finishing.dyeing_finishing.doctype.finished_product_return.finished_product_return";

function set_return_totals(frm) {
  const rows = frm.doc.items || [];
  frm.set_value("total_roll_count", rows.length);
  frm.set_value("total_weight", rows.reduce((sum, row) => sum + flt(row.return_weight), 0));
  frm.set_value("total_yard_qty", rows.reduce((sum, row) => sum + flt(row.return_yard_qty), 0));
}

function render_return_selector(frm) {
  const field = frm.get_field("select_rolls_html");
  if (!field?.$wrapper) return;
  const disabled = frm.doc.docstatus !== 0 || !frm.doc.production_flow_card;
  field.$wrapper.html(`
    <button type="button" class="btn btn-sm btn-primary finished-return-selector" ${disabled ? "disabled" : ""}>选择已出库成品卷</button>
    <span class="text-muted ml-2">可选择该流转卡下多张成品出库单的尚可退货卷。</span>`);
  field.$wrapper.off("click.finishedReturn").on("click.finishedReturn", ".finished-return-selector", () => select_return_rolls(frm));
}

function configure_return_items_grid(frm) {
  frm.set_df_property("items", "cannot_add_rows", true);
  frm.fields_dict.items?.grid?.refresh();
}

async function select_return_rolls(frm) {
  const existing = new Set((frm.doc.items || []).map(row => row.source_delivery_item));
  const dialog = new frappe.ui.form.MultiSelectDialog({
    doctype: "Finished Product Delivery Item", target: frm, setters: {}, add_filters_group: false,
    columns: ["匹号", "成品卷号", "尚可退重量(Kg)", "尚可退码数(Y)", "来源成品出库单"],
    primary_action_label: "添加所选退货卷",
    get_query: () => ({ query: `${RETURN_METHOD}.get_returnable_finished_rolls`, filters: {
      production_flow_card: frm.doc.production_flow_card, excluded_names: JSON.stringify([...existing]),
    }}),
    async action(selections) {
      const names = selections.filter(name => !existing.has(name));
      if (!names.length) { dialog.dialog.hide(); return; }
      const response = await frappe.call({ method: `${RETURN_METHOD}.get_returnable_roll_details`, args: { names } });
      (response.message || []).forEach(source => {
        const row = frm.add_child("items");
        Object.assign(row, {
          source_delivery_item: source.source_delivery_item, packing_receipt_item: source.packing_receipt_item,
          source_delivery: source.source_delivery, source_packing_receipt: source.source_packing_receipt,
          piece_no: source.piece_no, roll_no: source.roll_no, finished_batch_no: source.finished_batch_no,
          original_weight: source.weight, original_yard_qty: source.yard_qty,
          return_weight: source.remaining_weight, return_yard_qty: source.remaining_yard_qty,
          finished_grade: source.finished_grade, original_quality_flag: source.quality_flag,
          return_type: "整卷退货", inspection_status: "待检", disposal_decision: "未处理",
        });
      });
      frm.refresh_field("items"); set_return_totals(frm); dialog.dialog.hide();
    },
  });
  dialog.page_length = 1000;
  dialog.dialog.set_title("选择尚可退货成品卷");
  dialog.dialog.fields_dict.search_term.$wrapper.hide();
}

function update_return_type(frm, cdt, cdn) {
  const row = locals[cdt][cdn];
  const full = Math.abs(flt(row.return_weight) - flt(row.original_weight)) < 0.000001
    && Math.abs(flt(row.return_yard_qty) - flt(row.original_yard_qty)) < 0.000001;
  frappe.model.set_value(cdt, cdn, "return_type", full ? "整卷退货" : "部分退货");
  set_return_totals(frm);
}

frappe.ui.form.on("Finished Product Return", {
  setup(frm) {
    frm.set_query("production_flow_card", () => ({ filters: { docstatus: 1 } }));
    configure_return_items_grid(frm);
  },
  refresh(frm) {
    configure_return_items_grid(frm);
    render_return_selector(frm);
  },
  async production_flow_card(frm) {
    frm.clear_table("items"); frm.refresh_field("items"); set_return_totals(frm);
    if (!frm.doc.production_flow_card) { render_return_selector(frm); return; }
    const response = await frappe.call({ method: `${RETURN_METHOD}.get_return_flow_card_details`, args: { flow_card: frm.doc.production_flow_card } });
    const data = response.message || {};
    ["sales_order", "customer", "customer_name", "finished_item_code", "finished_batch_no", "finished_product_name",
      "finished_specification", "color_no", "color", "target_warehouse", "delivered_roll_count", "delivered_weight",
      "delivered_yard_qty", "previous_return_weight", "returnable_weight", "returnable_yard_qty"]
      .forEach(fieldname => frm.set_value(fieldname, data[fieldname] || ""));
    render_return_selector(frm);
  },
  items_remove(frm) { set_return_totals(frm); },
});

frappe.ui.form.on("Finished Product Return Item", {
  return_weight: update_return_type,
  return_yard_qty: update_return_type,
});
