const progress_query_filters = [
  {fieldname: "from_date", label: __("交货日期从"), fieldtype: "Date"},
  {fieldname: "to_date", label: __("交货日期至"), fieldtype: "Date"},
  {fieldname: "customer", label: __("客户名称"), fieldtype: "Link", options: "Customer"},
  {fieldname: "sales_order", label: __("染整销售订单"), fieldtype: "Link", options: "Dyeing Sales Order"},
  {fieldname: "flow_card", label: __("生产流转卡"), fieldtype: "Link", options: "Production Flow Card"},
  {fieldname: "production_status", label: __("生产状态"), fieldtype: "Select", options: "\n进行中\n已完成\n已关闭"},
  {fieldname: "current_progress_status", label: __("当前进度状态"), fieldtype: "Data"},
  {fieldname: "current_operation", label: __("当前工序"), fieldtype: "Link", options: "Production Operation"},
  {fieldname: "completion_status", label: __("入出库进度"), fieldtype: "Select", options: "\n未入库\n部分入库\n全部入库\n部分出库\n全部出库"},
  {fieldname: "overdue_only", label: __("仅显示逾期"), fieldtype: "Check", default: 0},
];

const progress_detail_columns = {
  progress: ["进度时间", "业务节点", "工序", "数量", "匹数", "码数", "来源单据", "操作人", "说明"],
  operations: ["顺序", "工序名称", "工序状态", "工序作业卡", "关联染色料单"],
  dyeing_materials: ["染色次数", "料单类型", "现场染色料单", "料单状态", "化验室配方", "配方版本", "生产机台", "计划用量(g)", "已领料(g)", "未领料(g)", "领料次数", "最近领料单"],
  packing: ["包装入库单", "入库日期", "包装状态", "匹数", "重量(Kg)", "码数(Y)", "库存凭证"],
  delivery: ["成品出库单", "出库日期", "出库状态", "匹数", "重量(Kg)", "码数(Y)", "库存凭证"],
};

const escape_progress_value = (value) => frappe.utils.escape_html(String(value ?? ""));
function document_link(value, doctype) {
  if (!value) return "";
  return `<a href="#" class="progress-document-link" data-doctype="${escape_progress_value(doctype)}" data-name="${escape_progress_value(value)}">${escape_progress_value(value)}</a>`;
}
function document_links(values, doctype) {
  return (values || []).map((value) => document_link(value, doctype)).join("、");
}
function render_empty_details(panel, message) {
  panel.find(".tab-pane").html(`<div class="production-progress-detail-empty">${escape_progress_value(message)}</div>`);
}

function detail_panel(report) {
  let panel = report.page.main.find(".production-progress-detail-panel");
  if (panel.length) return panel;
  report.page.main.append(`
    <div class="production-progress-detail-panel mt-4">
      <style>
        .production-progress-detail-panel{border:1px solid var(--border-color);border-radius:8px;background:var(--card-bg)}
        .production-progress-detail-header{padding:12px 16px;border-bottom:1px solid var(--border-color);display:flex;justify-content:space-between;align-items:center}
        .production-progress-detail-panel .nav-tabs{padding:0 12px}.production-progress-detail-body{min-height:260px;padding:12px 16px 18px;overflow:auto}
        .production-progress-detail-body table{min-width:900px;margin-bottom:0}.production-progress-detail-body th{white-space:nowrap;background:var(--subtle-fg)}
        .production-progress-detail-body td{white-space:nowrap;vertical-align:middle}.production-progress-detail-empty{color:var(--text-muted);text-align:center;padding:70px 10px}
        .production-progress-master-selected .dt-cell{background:var(--control-bg-on-gray)!important}
      </style>
      <div class="production-progress-detail-header"><div><b>生产流转卡进度明细</b><span class="selected-flow-card text-muted ml-2">请选择生产流转卡</span></div><button class="btn btn-xs btn-default open-flow-card" style="display:none">打开流转卡</button></div>
      <ul class="nav nav-tabs" role="tablist">
        <li class="nav-item"><a class="nav-link active" data-toggle="tab" href="#flow-progress-records">进度记录</a></li>
        <li class="nav-item"><a class="nav-link" data-toggle="tab" href="#flow-operation-progress">工序进度</a></li>
        <li class="nav-item"><a class="nav-link" data-toggle="tab" href="#flow-dyeing-materials">染色用料</a></li>
        <li class="nav-item"><a class="nav-link" data-toggle="tab" href="#flow-packing-progress">包装入库</a></li>
        <li class="nav-item"><a class="nav-link" data-toggle="tab" href="#flow-delivery-progress">成品出库</a></li>
      </ul>
      <div class="tab-content production-progress-detail-body">
        <div class="tab-pane active" id="flow-progress-records"></div><div class="tab-pane" id="flow-operation-progress"></div><div class="tab-pane" id="flow-dyeing-materials"></div>
        <div class="tab-pane" id="flow-packing-progress"></div><div class="tab-pane" id="flow-delivery-progress"></div>
      </div>
    </div>`);
  panel = report.page.main.find(".production-progress-detail-panel");
  panel.on("click", ".nav-link", (event) => {
    event.preventDefault();
    const link = $(event.currentTarget);
    const target = link.attr("href");
    panel.find(".nav-link").removeClass("active").attr("aria-selected", "false");
    link.addClass("active").attr("aria-selected", "true");
    panel.find(".tab-pane").removeClass("active show").hide();
    panel.find(target).addClass("active show").show();
  });
  panel.on("click", ".progress-document-link", (event) => { event.preventDefault(); frappe.set_route("Form", event.currentTarget.dataset.doctype, event.currentTarget.dataset.name); });
  panel.on("click", ".open-flow-card", () => { if (report._selected_progress_flow_card) frappe.set_route("Form", "Production Flow Card", report._selected_progress_flow_card); });
  render_empty_details(panel, "请在上方主表中选择一张生产流转卡");
  return panel;
}

function render_table(target, columns, rows) {
  if (!rows.length) { target.html('<div class="production-progress-detail-empty">暂无记录</div>'); return; }
  const head = columns.map((column) => `<th>${column}</th>`).join("");
  const body = rows.map((row) => `<tr>${row.map((value) => `<td>${value ?? ""}</td>`).join("")}</tr>`).join("");
  target.html(`<table class="table table-bordered table-hover table-sm"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`);
}

function render_progress_details(panel, result) {
  render_table(panel.find("#flow-progress-records"), progress_detail_columns.progress, (result.progress || []).map((row) => [
    escape_progress_value(row.progress_time), escape_progress_value(row.progress_status), escape_progress_value(row.operation), `${escape_progress_value(row.quantity)} ${escape_progress_value(row.uom)}`,
    escape_progress_value(row.roll_count), escape_progress_value(row.yard_qty), document_link(row.source_document, row.source_doctype), escape_progress_value(row.operator), escape_progress_value(row.description),
  ]));
  render_table(panel.find("#flow-operation-progress"), progress_detail_columns.operations, (result.operations || []).map((row) => [escape_progress_value(row.sequence_no), escape_progress_value(row.operation_name), escape_progress_value(row.operation_status), document_link(row.job_card, "Job Card"), document_links(row.related_material_sheets, "Site Dyeing Material Sheet")]));
  render_table(panel.find("#flow-dyeing-materials"), progress_detail_columns.dyeing_materials, (result.dyeing_materials || []).map((row) => [
    escape_progress_value(row.dyeing_sequence), escape_progress_value(row.material_sheet_type), document_link(row.name, "Site Dyeing Material Sheet"), escape_progress_value(row.material_sheet_status),
    document_link(row.laboratory_recipe, "Laboratory Recipe"), escape_progress_value(row.recipe_version), document_link(row.production_resource, "Production Resource"),
    escape_progress_value(row.planned_qty_g), escape_progress_value(row.issued_qty_g), escape_progress_value(row.remaining_qty_g), escape_progress_value(row.issue_count), document_link(row.latest_issue, "Site Dyeing Material Issue"),
  ]));
  render_table(panel.find("#flow-packing-progress"), progress_detail_columns.packing, (result.packing || []).map((row) => [document_link(row.name, "Finished Product Packing Receipt"), escape_progress_value(row.packing_date), escape_progress_value(row.packing_status), escape_progress_value(row.total_roll_count), escape_progress_value(row.total_weight), escape_progress_value(row.total_yard_qty), document_link(row.stock_entry, "Stock Entry")]));
  render_table(panel.find("#flow-delivery-progress"), progress_detail_columns.delivery, (result.delivery || []).map((row) => [document_link(row.name, "Finished Product Delivery"), escape_progress_value(row.delivery_date), escape_progress_value(row.delivery_status), escape_progress_value(row.total_roll_count), escape_progress_value(row.total_weight), escape_progress_value(row.total_yard_qty), document_link(row.stock_entry, "Stock Entry")]));
}

function load_progress_details(report, flow_card) {
  if (!flow_card || (report._selected_progress_flow_card === flow_card && report._progress_detail_loaded)) return;
  const panel = detail_panel(report); report._selected_progress_flow_card = flow_card; report._progress_detail_loaded = false;
  panel.find(".selected-flow-card").text(flow_card); panel.find(".open-flow-card").show(); render_empty_details(panel, "正在加载进度明细…");
  frappe.call({method: "dyeing_finishing.dyeing_finishing.report.production_flow_card_progress_query.production_flow_card_progress_query.get_progress_details", args: {flow_card}, callback(response) {
    if (report._selected_progress_flow_card !== flow_card) return;
    report._progress_detail_loaded = true; render_progress_details(panel, response.message || {});
  }});
}

function bind_master_rows(report) {
  const wrapper = report.$report || report.page.main.find(".report-wrapper");
  wrapper.off("click.production-progress-master").on("click.production-progress-master", ".dt-row[data-row-index]", function () {
    const index = Number(this.dataset.rowIndex); let row = report.data?.[index];
    if (!row?.flow_card && index > 0) row = report.data?.[index - 1];
    if (!row?.flow_card) return;
    wrapper.find(".dt-row").removeClass("production-progress-master-selected"); $(this).addClass("production-progress-master-selected"); load_progress_details(report, row.flow_card);
  });
  if (report._selected_progress_flow_card && !(report.data || []).some((row) => row.flow_card === report._selected_progress_flow_card)) { report._selected_progress_flow_card = null; report._progress_detail_loaded = false; }
  if (!report._selected_progress_flow_card && report.data?.[0]?.flow_card) load_progress_details(report, report.data[0].flow_card);
}

dyeing_finishing_report_layout.register({
  report_name: "Production Flow Card Progress Query", filters: progress_query_filters,
  datatable_options: {cellHeight: 44},
  onload(report) {
    detail_panel(report);
    // Bind directly as well as through after_datatable_render.  This keeps the
    // master/detail interaction working when a browser still has an older
    // cached copy of the shared report-layout helper.
    bind_master_rows(report);
    window.setTimeout(() => bind_master_rows(report), 500);
    window.setTimeout(() => bind_master_rows(report), 1500);
  },
  after_datatable_render(report) { window.setTimeout(() => bind_master_rows(report), 0); },
});
