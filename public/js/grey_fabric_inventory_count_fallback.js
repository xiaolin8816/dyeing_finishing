/* eslint-disable */
(() => {
	const DOCTYPE = "Grey Fabric Inventory Count";
	const LAST_VALID_FORM_KEY = "dyeing_finishing.grey_fabric_inventory_count.last_form";
	const RECOVERY_ATTEMPT_KEY = "dyeing_finishing.grey_fabric_inventory_count.recovery_attempt";
	let timer;
	let form_diagnostic_timer;
	let request_started = false;
	let invalid_route_warning_shown = false;
	let frontend_error_shown = false;
	let diagnostic_route_key = "";

	function show_frontend_error(title, detail) {
		const route = frappe.get_route() || [];
		if (String(route[0] || "").toLowerCase() !== "form" || route[1] !== DOCTYPE || frontend_error_shown) return;
		frontend_error_shown = true;
		const $notice = $('<div class="grey-fabric-count-form-diagnostic" role="alert"></div>').css({
			position: "fixed", top: "72px", right: "16px", zIndex: 100000,
			maxWidth: "min(720px, calc(100vw - 32px))", maxHeight: "45vh", overflow: "auto",
			padding: "14px 18px", color: "#842029", background: "#f8d7da",
			border: "1px solid #f1aeb5", borderRadius: "6px", boxShadow: "0 4px 16px #0003",
			whiteSpace: "pre-wrap", overflowWrap: "anywhere",
		});
		$notice.append($('<div style="font-weight:700;margin-bottom:6px"></div>').text(title));
		$notice.append($('<div></div>').text(String(detail || "未知前端错误")));
		$(document.body).append($notice);
	}

	window.addEventListener("error", (event) => {
		const detail = event.error?.stack || `${event.message || "脚本错误"}（${event.filename || "未知文件"}:${event.lineno || 0}）`;
		console.error("胚布盘点表前端异常", event.error || event.message);
		show_frontend_error("盘点表单初始化时发生前端错误", detail);
	});
	window.addEventListener("unhandledrejection", (event) => {
		const reason = event.reason;
		const detail = reason?.stack || reason?.message || String(reason || "未处理的异步错误");
		console.error("胚布盘点表异步异常", reason);
		show_frontend_error("盘点表单初始化时发生异步错误", detail);
	});

	// Frappe route calls are guarded above, but a normal anchor/location change
	// can bypass frappe.set_route. Block malformed navigations while this form is open.
	window.navigation?.addEventListener?.("navigate", (event) => {
		let destination;
		try {
			destination = new URL(event.destination.url);
		} catch (error) {
			return;
		}
		const current_is_count = window.location.pathname.includes("grey-fabric-inventory-count");
		const destination_is_invalid = destination.origin === window.location.origin
			&& /(?:^|\/)undefined(?:\/|$)/i.test(destination.pathname);
		if (!current_is_count || !destination_is_invalid) return;
		event.preventDefault();
		const detail = `已阻止跳转到无效地址：${destination.pathname}`;
		console.error("拦截到绕过前端路由函数的无效导航", {from: window.location.href, to: destination.href});
		show_frontend_error("已阻止页面跳到无效地址", detail);
	});

	// Prevent broken route arguments from sending Desk to a blank `/undefined` page.
	function guard_invalid_form_route() {
		const router = frappe.router;
		if (!router?.set_route || router.set_route.__grey_fabric_count_route_guard) return;
		const original_set_route = router.set_route.bind(router);
		const guarded_set_route = function (...args) {
			let route = args.length === 1 && Array.isArray(args[0]) ? args[0] : args;
			if (route.length === 1 && typeof route[0] === "string") {
				route = route[0].split("/");
			}
			if (route[0] === "desk" || route[0] === "app") route = route.slice(1);
			const current_route = frappe.get_route?.() || [];
			const count_route = route[1] === DOCTYPE
				|| route[0] === "grey-fabric-inventory-count"
				|| current_route[1] === DOCTYPE
				|| window.location.pathname.includes("grey-fabric-inventory-count");
			const has_invalid_segment = route.some((part) =>
				part == null || String(part).trim().toLowerCase() === "undefined");
			const is_incomplete_count_form = route[0] === "Form" && route[1] === DOCTYPE
				&& (!route[2] || String(route[2]).trim().toLowerCase() === "undefined");
			if (count_route && (has_invalid_segment || is_incomplete_count_form)) {
				const detail = `目标路由：${JSON.stringify(route)}\n调用位置：${new Error().stack || "未知"}`;
				console.error("已拦截胚布盘点表无效路由", {route, stack: detail});
				if (!invalid_route_warning_shown) {
					invalid_route_warning_shown = true;
					frappe.show_alert({message: "系统已拦截胚布盘点表的无效跳转，避免打开空白页面。", indicator: "orange"});
				}
				return Promise.resolve();
			}
			return original_set_route(...args);
		};
		guarded_set_route.__grey_fabric_count_route_guard = true;
		router.set_route = guarded_set_route;
	}

	function recover_invalid_route() {
		const route = frappe.get_route() || [];
		const view = String(route[0] || "").toLowerCase();
		const is_count_form = view === "form" && route[1] === DOCTYPE;
		const document_name = is_count_form ? route.slice(2).join("/") : "";
		const has_invalid_route = !route.length || route.some((part) =>
			part == null || String(part).trim().toLowerCase() === "undefined");

		if (is_count_form && document_name && document_name.toLowerCase() !== "undefined") {
			window.sessionStorage.setItem(LAST_VALID_FORM_KEY, document_name);
			return;
		}
		if (!has_invalid_route) return;

		const last_document = window.sessionStorage.getItem(LAST_VALID_FORM_KEY);
		console.error("检测到无效页面路由，正在自动恢复", {route, last_document});
		if (!invalid_route_warning_shown) {
			invalid_route_warning_shown = true;
			frappe.show_alert({message: "检测到无效页面地址，正在恢复刚才打开的胚布盘点单。", indicator: "orange"});
		}
		window.setTimeout(() => {
			if (last_document) {
				const attempted_document = window.sessionStorage.getItem(RECOVERY_ATTEMPT_KEY);
				if (attempted_document === last_document) {
					frappe.set_route("List", DOCTYPE);
					return;
				}
				window.sessionStorage.setItem(RECOVERY_ATTEMPT_KEY, last_document);
				const slug = frappe.router?.slug ? frappe.router.slug(DOCTYPE) : "grey-fabric-inventory-count";
				window.location.replace(`/desk/${slug}/${encodeURIComponent(last_document)}`);
			} else {
				frappe.set_route("List", DOCTYPE);
			}
		}, 0);
	}

	function show_form_render_diagnostic() {
		const route = frappe.get_route() || [];
		const is_count_form = String(route[0] || "").toLowerCase() === "form" && route[1] === DOCTYPE;
		const next_route_key = is_count_form ? route.slice(0, 3).join("|") : "";
		if (next_route_key !== diagnostic_route_key) {
			diagnostic_route_key = next_route_key;
			frontend_error_shown = false;
			$(".grey-fabric-count-form-diagnostic").remove();
		}
		if (!is_count_form) return;
		const route_name = route.slice(2).join("/");
		window.clearTimeout(form_diagnostic_timer);
		form_diagnostic_timer = window.setTimeout(() => {
			form_diagnostic_timer = null;
			if ((frappe.get_route() || []).slice(0, 2).join("|") !== `Form|${DOCTYPE}`) return;
			const form = window.cur_frm;
			if (form?.__grey_count_rendering) return;
			const doc_matches = form?.doctype === DOCTYPE && form?.doc?.name === route_name;
			if (doc_matches && form.__grey_count_controls_rebuilt_for !== form.doc.name) {
				form.__grey_count_controls_rebuilt = false;
				form.__grey_count_controls_rebuilt_for = form.doc.name;
				form.__grey_count_rebuild_result = null;
			}
			const has_form_layout = Boolean(document.querySelector(".form-layout"));
			const control_entries = Object.entries(form?.fields_dict || {}).filter(([, control]) => {
				const fieldtype = control?.df?.fieldtype;
				return fieldtype && !["Section Break", "Column Break", "Tab Break", "Fold", "Page Break"].includes(fieldtype);
			});
			const control_states = control_entries.map(([fieldname, control]) => {
				const element = control?.$wrapper?.get?.(0);
				const style = element ? window.getComputedStyle(element) : null;
				const visible = Boolean(element && element.getClientRects().length && style.display !== "none" && style.visibility !== "hidden" && style.opacity !== "0");
				const label = element?.querySelector(".control-label, .grid-field > label");
				const input = element?.querySelector("input:not([type=hidden]), textarea, select, .like-disabled-input, .grid-heading-row");
				const label_visible = Boolean(label && label.getClientRects().length && label.textContent.trim());
				const input_visible = Boolean(input && input.getClientRects().length && window.getComputedStyle(input).visibility !== "hidden");
				let status = control.disp_status || "未刷新";
				try { status = control.get_status?.() || status; } catch (error) { status = `状态异常：${error?.message || error}`; }
				return {fieldname, fieldtype: control.df.fieldtype, status, disp_status: control.disp_status || "未刷新", control_class: control.constructor?.name || "未知", refresh_method: typeof control.refresh, refresh_input: typeof control.refresh_input, has_input: Boolean(control.has_input), has_input_element: Boolean(control.$input?.length), input_area_ready: Boolean(control.input_area), visible, label_visible, input_visible, wrapper_class: element?.className || "未生成", display: style?.display || "无", visibility: style?.visibility || "无", height: element?.getBoundingClientRect?.().height || 0};
			});
			const visible_control_count = control_states.filter((item) => item.visible).length;
			const rendered_control_count = control_states.filter((item) => item.label_visible || item.input_visible).length;
			const expected_minimum = Math.min(4, control_entries.length);
			if (doc_matches && has_form_layout && control_entries.length > 0 && rendered_control_count >= expected_minimum) {
				window.sessionStorage.removeItem(RECOVERY_ATTEMPT_KEY);
				return;
			}
			if (doc_matches && has_form_layout && control_entries.length && !form.__grey_count_controls_rebuilt && typeof form.layout?.replace_field === "function") {
				form.__grey_count_controls_rebuilt = true;
				form.__grey_count_rendering = true;
				form.__grey_count_rebuild_result = [];
				try {
					// Recreate broken controls through Frappe's own layout API with render enabled.
					// Repeatedly refreshing the old objects cannot initialize their missing UI.
					form.layout.doc = form.doc;
					control_entries.forEach(([fieldname, control]) => {
						if (!control?.df || !control?.$wrapper) return;
						try {
							const replacement_df = Object.assign({}, control.df);
							form.layout.replace_field(fieldname, replacement_df, true);
							const replacement = form.layout.fields_dict[fieldname];
							form.__grey_count_rebuild_result.push({fieldname, replaced: replacement !== control, disp_status: replacement?.disp_status || "未刷新", has_input: Boolean(replacement?.has_input), has_input_element: Boolean(replacement?.$input?.length), wrapper_html_length: replacement?.$wrapper?.html?.().length || 0});
						} catch (error) {
							control.__grey_count_render_error = error?.stack || error?.message || String(error);
							form.__grey_count_rebuild_result.push({fieldname, error: control.__grey_count_render_error});
							console.error("胚布盘点表字段重建失败", fieldname, error);
						}
					});
					window.setTimeout(() => {
					try {
						if (typeof form.layout.refresh_dependency === "function") form.layout.refresh_dependency();
						if (typeof form.layout.refresh_sections === "function") form.layout.refresh_sections();
					} finally {
						form.__grey_count_rendering = false;
					}
						show_form_render_diagnostic();
					}, 900);
					return;
				} catch (error) {
					form.__grey_count_rendering = false;
					show_frontend_error("刷新盘点表字段失败", error?.stack || error?.message || error);
					return;
				}
			}
			if (doc_matches && has_form_layout && (!control_entries.length || rendered_control_count < expected_minimum)) {
				const summary = [
					`字段控件定义数：${control_states.length}`,
					`可见字段外框数：${visible_control_count}`,
					`实际渲染标签/输入框数：${rendered_control_count}`,
					`表单字段权限：${JSON.stringify(form?.perm || [])}`,
					`初始化状态：${JSON.stringify({setup_done: Boolean(form?.setup_done), layout: Boolean(form?.layout), replace_field: typeof form?.layout?.replace_field, rebuilt: Boolean(form?.__grey_count_controls_rebuilt)})}`,
					`控件重建结果：${JSON.stringify(form?.__grey_count_rebuild_result || [])}`,
					`字段渲染状态：${JSON.stringify(control_states.slice(0, 12))}`,
					`字段渲染异常：${JSON.stringify(control_entries.filter(([, control]) => control?.__grey_count_render_error).map(([fieldname, control]) => ({fieldname, error: control.__grey_count_render_error})))}`,
				].join("；");
				show_frontend_error("表单分区已生成，但字段控件没有显示", summary);
				console.error("胚布盘点表字段显示诊断", {route, control_states, form});
				return;
			}
			const has_read_permission = Boolean(form?.has_read_permission?.());
			if (document.querySelector(".grey-fabric-count-form-diagnostic")) return;
			const $target = $(".layout-main-section-wrapper").last();
			if (!$target.length) return;
			const reload_state = (() => {
				try { return typeof form?.check_reload === "function" ? String(form.check_reload()) : "不可用"; }
				catch (error) { return `检查异常：${error?.message || error}`; }
			})();
			const details = [
				`路由单号：${route_name || "（空）"}`,
				`表单控制器：${form?.doctype || "未创建"}`,
				`当前表单单号：${form?.doc?.name || "未加载"}`,
				`表单布局：${has_form_layout ? "已生成" : "未生成"}`,
				`表单初始化：${form?.setup_done ? "已完成" : "未完成"}`,
				`布局对象：${form?.layout ? "已创建" : "未创建"}`,
				`读取权限：${has_read_permission ? "允许" : "未确认/未允许"}`,
				`刷新检查：${reload_state}`,
				`页面容器：${document.querySelector(".layout-main-section-wrapper") ? "已创建" : "未创建"}`,
			].join("；");
			show_frontend_error("盘点单数据已返回，但页面表单未完成渲染", details);
			console.error("胚布盘点表单渲染诊断", {route, doc_matches, has_form_layout, has_read_permission, setup_done: form?.setup_done, layout: form?.layout, reload_state, form});
		}, 2500);
	}

	function is_count_list() {
		const route = frappe.get_route() || [];
		return (route[0] === "List" && route[1] === DOCTYPE)
			|| window.location.pathname.endsWith("/desk/grey-fabric-inventory-count");
	}

	function clear_fallback() {
		$(".grey-fabric-count-list-fallback").remove();
		request_started = false;
	}

	function get_count_list_main() {
		const listview = window.cur_list;
		if (!listview || listview.doctype !== DOCTYPE) return $();
		return $(listview.page?.wrapper || listview.$page || []).find(".layout-main-section-wrapper").last();
	}

	function schedule_fallback() {
		window.clearTimeout(timer);
		if (!is_count_list()) {
			clear_fallback();
			return;
		}
		timer = window.setTimeout(load_fallback, 3500);
	}

	function load_fallback() {
		if (!is_count_list()) {
			clear_fallback();
			return;
		}
		if (request_started) return;
		const $main = get_count_list_main();
		if (!$main.length || $main.find(".grey-fabric-count-list-fallback").length) return;

		const $visible_rows = $main.find(".frappe-list .list-row:not(.list-row-head)").filter(":visible");
		if ($visible_rows.length) return;

		request_started = true;
		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: DOCTYPE,
				fields: ["name", "count_date", "warehouse", "customer", "customer_name", "status"],
				order_by: "creation desc",
				limit_page_length: 100,
			},
		}).then((response) => {
			if (!is_count_list()) {
				clear_fallback();
				return;
			}
			const rows = response.message || [];
			const $box = $('<div class="alert alert-warning grey-fabric-count-list-fallback"></div>');
			const $message = $("<div></div>").text(rows.length
				? "标准列表未正常显示，以下是系统自动读取的盘点记录；点击单号可打开单据。"
				: "标准列表未正常显示，后台直查也没有返回记录，请检查当前用户的数据权限。");
			const $table = $('<div class="table-responsive mt-2"><table class="table table-bordered table-sm"><thead><tr><th>单号</th><th>盘点日期</th><th>仓库</th><th>客户</th><th>状态</th></tr></thead><tbody></tbody></table></div>');
			const $body = $table.find("tbody");
			rows.forEach((row) => {
				const $tr = $("<tr></tr>");
				const $link = $("<a href=\"#\"></a>").text(row.name || "");
				$link.on("click", (event) => {
					event.preventDefault();
					event.stopPropagation();
					if (row.name) frappe.set_route("Form", DOCTYPE, row.name);
				});
				$("<td></td>").append($link).appendTo($tr);
				["count_date", "warehouse", "customer_name", "status"].forEach((field) => {
					$("<td></td>").text(row[field] || (field === "customer_name" ? row.customer : "") || "").appendTo($tr);
				});
				$body.append($tr);
			});
			if (!rows.length) $body.append('<tr><td colspan="5">暂无记录</td></tr>');
			$box.append($message, $table);
			$main.prepend($box);
		}).catch((error) => {
			request_started = false;
			console.error("胚布盘点表备用列表读取失败", error);
		});
	}

	guard_invalid_form_route();
	frappe.router?.on?.("change", schedule_fallback);
	frappe.router?.on?.("change", () => window.setTimeout(recover_invalid_route, 0));
	frappe.router?.on?.("change", show_form_render_diagnostic);
	$(document).on("page-change", show_form_render_diagnostic);
	$(document).on("page-change", schedule_fallback);
	schedule_fallback();
	show_form_render_diagnostic();
})();
