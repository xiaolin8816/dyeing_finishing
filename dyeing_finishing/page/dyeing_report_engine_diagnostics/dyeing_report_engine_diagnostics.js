frappe.pages["dyeing-report-engine-diagnostics"].on_page_load = function (wrapper) {
	const page=frappe.ui.make_app_page({parent:wrapper,title:"报表引擎诊断",single_column:true});
	page.set_primary_action("重新检测",load,"refresh");
	page.set_secondary_action("生成中文测试 PDF",smoke,"printer");
	const root=$("<div class='mt-4'></div>").appendTo(page.main);
	$("<style>").text(`.dred-summary{padding:14px 16px;border-radius:8px;margin-bottom:12px}.dred-ok{background:#dcfce7;color:#166534}.dred-error{background:#fee2e2;color:#991b1b}.dred-row{display:grid;grid-template-columns:220px 90px 1fr;gap:12px;padding:12px;border-bottom:1px solid var(--border-color)}.dred-card{border:1px solid var(--border-color);border-radius:8px;background:var(--card-bg);overflow:hidden}.dred-status{font-weight:700}`).appendTo(page.main);
	const esc=v=>frappe.utils.escape_html(String(v==null?"":v));
	async function load(){root.html('<div class="text-muted">正在检测…</div>');const r=await frappe.call({method:"dyeing_finishing.dyeing_finishing.page.dyeing_report_engine_diagnostics.dyeing_report_engine_diagnostics.get_diagnostics"});const d=r.message;root.html(`<div class="dred-summary ${d.healthy?"dred-ok":"dred-error"}">${d.healthy?"报表引擎已就绪，可以正常迁移和打印。":"检测到未就绪项，请根据下方详情处理。"}</div><div class="dred-card">${d.checks.map(x=>`<div class="dred-row"><b>${esc(x.label)}</b><span class="dred-status ${x.status==="ok"?"text-success":"text-danger"}">${x.status==="ok"?"正常":"异常"}</span><span>${esc(x.detail)}</span></div>`).join("")}</div>`);}
	async function smoke(){const r=await frappe.call({method:"dyeing_finishing.dyeing_finishing.page.dyeing_report_engine_diagnostics.dyeing_report_engine_diagnostics.run_smoke_test",freeze:true,freeze_message:"正在生成中文测试 PDF…"});frappe.msgprint({title:"试打成功",message:`${r.message.message}<br>PDF 大小：${r.message.pdf_bytes} 字节`,indicator:"green"});load();}
	load();
};
