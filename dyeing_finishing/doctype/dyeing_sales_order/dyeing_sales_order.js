function dyeing_order_specification(row) {
    const width = String(row.finished_width || "").trim();
    const gsm = String(row.finished_gsm || "").trim();
    const gsmValue = gsm ? `${gsm}${row.finished_gsm_uom || ""}` : "";
    return [width, gsmValue].filter(Boolean).join("*");
}

function update_dyeing_order_row(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    frappe.model.set_value(cdt, cdn, "finished_specification", dyeing_order_specification(row));
    frappe.model.set_value(cdt, cdn, "amount", flt(row.qty) * flt(row.rate));
    update_dyeing_order_totals(frm);
}

function update_dyeing_order_totals(frm) {
    const items = frm.doc.items || [];
    frm.set_value("total_qty", items.reduce((sum, row) => sum + flt(row.qty), 0));
    frm.set_value("total_amount", items.reduce((sum, row) => sum + flt(row.amount), 0));
}

function requirement_config(type) {
    return type === "process"
        ? {doctype: "Process Requirement", table: "process_requirements", link: "process_requirement", name: "process_requirement_name"}
        : {doctype: "Packaging Requirement", table: "packaging_requirements", link: "packaging_requirement", name: "packaging_requirement_name"};
}

async function select_dyeing_requirements(frm, type) {
    if (frm.doc.docstatus === 2) return;
    const config = requirement_config(type);
    await frappe.model.with_doctype(config.doctype);
    const dialog = new frappe.ui.form.MultiSelectDialog({
        doctype: config.doctype,
        target: frm,
        setters: {[config.name]: ""},
        primary_action_label: "添加所选要求",
        get_query: () => ({filters: {disabled: 0}}),
        add_filters_group: false,
        action(selections) {
            const existing = new Set((frm.doc[config.table] || []).map((row) => row[config.link]));
            selections.forEach((value) => {
                if (existing.has(value)) return;
                const row = frm.add_child(config.table);
                row[config.link] = value;
                existing.add(value);
                frappe.db.get_value(config.doctype, value, [config.name, "description"]).then((result) => {
                    frappe.model.set_value(row.doctype, row.name, config.name, result.message?.[config.name] || "");
                    frappe.model.set_value(row.doctype, row.name, "description", result.message?.description || "");
                });
            });
            frm.refresh_field(config.table);
            dialog.dialog.hide();
        },
    });
    dialog.page_length = 1000;
    dialog.dialog.set_title(type === "process" ? "选择加工要求" : "选择包装要求");
    const selected = new Set((frm.doc[config.table] || []).map(row => row[config.link]));
    const render = dialog.render_result_list.bind(dialog);
    const label_columns = () => {
        dialog.$results.find(".list-item--head .list-item__content:eq(1) span").text("编码");
        dialog.$results.find(".list-item--head .list-item__content:eq(2) span").text("名称");
    };
    dialog.render_result_list = (results, more, empty) => {
        render(results.filter(row => !selected.has(row.name)).sort((a, b) =>
            a.name.localeCompare(b.name, undefined, {numeric: true})), more, empty);
        label_columns();
    };
    label_columns();
    dialog.get_results();
}

function set_dyeing_requirement_tab(frm, active) {
    frm._dyeing_requirement_tab = active;
    const tables = {
        process: "process_requirements",
        packaging: "packaging_requirements",
    };
    Object.entries(tables).forEach(([tab, fieldname]) => {
        const field = frm.get_field(fieldname);
        if (field?.$wrapper) field.$wrapper.toggle(tab === active);
    });
    const field = frm.get_field("requirements_html");
    if (!field?.$wrapper) return;
    const editable = frm.doc.docstatus !== 2;
    field.$wrapper.html(`
        <div class="dyeing-requirement-tabs">
            <button type="button" class="btn btn-sm ${active === "process" ? "btn-primary" : "btn-default"}" data-requirement-tab="process">加工要求</button>
            <button type="button" class="btn btn-sm ${active === "packaging" ? "btn-primary" : "btn-default"}" data-requirement-tab="packaging">包装要求</button>
            <button type="button" class="btn btn-sm btn-default" data-requirement-select="${active}" ${editable ? "" : "disabled"}>选择${active === "process" ? "加工要求" : "包装要求"}</button>
        </div>`);
    field.$wrapper.off("click.dyeingOrderTabs")
        .on("click.dyeingOrderTabs", "[data-requirement-tab]", function () {
            set_dyeing_requirement_tab(frm, $(this).data("requirement-tab"));
        })
        .on("click.dyeingOrderTabs", "[data-requirement-select]", function () {
            if (editable) select_dyeing_requirements(frm, $(this).data("requirement-select"));
        });
}

function change_reason_options(frm) {
    const oldDoc = frm.__dyeing_order_snapshot || {};
    const current = frm.doc || {};
    const suggestions = [];
    if ((current.customer || "") !== (oldDoc.customer || "") || (current.customer_order_no || "") !== (oldDoc.customer_order_no || "")) suggestions.push("客户资料更正");
    if ((current.delivery_date || "") !== (oldDoc.delivery_date || "")) suggestions.push("客户交期调整");
    const oldItems = new Map((oldDoc.items || []).map((row) => [row.name, row]));
    const changed = (fields) => (current.items || []).some((row) => {
        const oldRow = oldItems.get(row.name) || {};
        return fields.some((fieldname) => String(row[fieldname] || "") !== String(oldRow[fieldname] || ""));
    });
    if (changed(["qty", "uom", "rate"])) suggestions.push("订单数量调整");
    if (changed(["item_code", "color_no", "color", "finished_product_name", "process_type", "finished_width", "finished_gsm", "finished_gsm_uom"])) suggestions.push("产品资料调整");
    if (JSON.stringify(current.process_requirements || []) !== JSON.stringify(oldDoc.process_requirements || [])) suggestions.push("工艺要求调整");
    if (JSON.stringify(current.packaging_requirements || []) !== JSON.stringify(oldDoc.packaging_requirements || [])) suggestions.push("包装要求调整");
    if ((current.order_remark || "") !== (oldDoc.order_remark || "")) suggestions.push("订单备注补充");
    const unique = [...new Set(suggestions)];
    const recommended = unique.length > 1 ? "综合调整" : (unique[0] || "录入错误更正");
    return [recommended, "客户要求变更", "录入错误更正", "产品资料调整", "订单数量调整", "客户交期调整", "工艺要求调整", "包装要求调整", "生产现场调整", "订单备注补充", "综合调整", "其他"].filter((value, index, array) => array.indexOf(value) === index);
}

function confirm_submitted_order_change(frm) {
    return new Promise((resolve) => {
        const options = change_reason_options(frm);
        const dialog = new frappe.ui.Dialog({
            title: "订单变更确认",
            fields: [
                {fieldname: "notice", fieldtype: "HTML", options: "<p>系统将记录本次变更，并同步更新关联的生产流转卡。</p>"},
                {fieldname: "reason", fieldtype: "Select", label: "修改原因", options: options.join("\n"), default: options[0], reqd: 1},
                {fieldname: "note", fieldtype: "Small Text", label: "补充说明"},
            ],
            primary_action_label: "确认修改并保存",
            primary_action(values) {
                if (values.reason === "其他" && !String(values.note || "").trim()) {
                    frappe.msgprint("选择“其他”时必须填写补充说明。");
                    return;
                }
                frm.doc.change_reason = values.reason;
                frm.doc.change_note = values.note || "";
                frm.__change_reason_confirmed = true;
                dialog.hide();
                resolve();
            },
        });
        dialog.show();
        dialog.$wrapper.on("hidden.bs.modal", () => {
            if (!frm.__change_reason_confirmed) {
                frappe.validated = false;
                resolve(false);
            }
        });
    });
}

frappe.ui.form.on("Dyeing Sales Order", {
    setup(frm) {
        if (frm.is_new() && !frm.doc.company) {
            frm.set_value("company", frappe.defaults.get_user_default("Company"));
        }
        frm.set_query("item_code", "items", () => ({
            filters: {
                item_group: "胚布",
                disabled: 0,
            },
        }));
        frm.set_query("color_no", "items", () => ({
            filters: {customer_name: frm.doc.customer || "__no_customer__", status: "启用"},
        }));
    },
    refresh(frm) {
        set_dyeing_requirement_tab(frm, frm._dyeing_requirement_tab || "process");
        frm.__dyeing_order_snapshot = JSON.parse(JSON.stringify(frm.doc));
        frm.__change_reason_confirmed = false;
    },
    before_save(frm) {
        if (frm.doc.docstatus === 1 && !frm.__change_reason_confirmed) {
            return confirm_submitted_order_change(frm);
        }
    },
    after_save(frm) {
        frm.__dyeing_order_snapshot = JSON.parse(JSON.stringify(frm.doc));
        frm.__change_reason_confirmed = false;
    },
    customer(frm) {
        (frm.doc.items || []).forEach((row) => {
            if (row.color_no) frappe.model.set_value(row.doctype, row.name, "color_no", "");
        });
    },
    delivery_date(frm) {
        (frm.doc.items || []).forEach((row) => {
            if (!row.delivery_date) frappe.model.set_value(row.doctype, row.name, "delivery_date", frm.doc.delivery_date);
        });
    },
});

frappe.ui.form.on("Dyeing Sales Order Item", {
    items_add(frm, cdt, cdn) {
        frappe.model.set_value(cdt, cdn, "delivery_date", frm.doc.delivery_date);
    },
    items_remove(frm) { update_dyeing_order_totals(frm); },
    qty: update_dyeing_order_row,
    rate: update_dyeing_order_row,
    finished_width: update_dyeing_order_row,
    finished_gsm: update_dyeing_order_row,
    finished_gsm_uom: update_dyeing_order_row,
    color_no(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.color_no) {
            frappe.model.set_value(cdt, cdn, "color", "");
            frappe.model.set_value(cdt, cdn, "finished_product_name", "");
            return;
        }
        frappe.db.get_value("Color Master", row.color_no, ["color_name", "product_name"]).then((result) => {
            frappe.model.set_value(cdt, cdn, "color", result.message?.color_name || "");
            frappe.model.set_value(cdt, cdn, "finished_product_name", result.message?.product_name || "");
        });
    },
});
