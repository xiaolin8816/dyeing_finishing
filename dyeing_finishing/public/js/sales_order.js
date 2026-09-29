function make_finished_specification(row) {
    const width = String(row.custom_finished_width || "").trim();
    const gsm = String(row.custom_finished_gsm || "").trim();
    const gsm_uom = String(row.custom_finished_gsm_uom || "").trim();
    const gsm_value = gsm ? `${gsm}${gsm_uom}` : "";
    return [width, gsm_value].filter(Boolean).join("*");
}

function update_finished_specification(cdt, cdn) {
    const row = locals[cdt][cdn];
    frappe.model.set_value(cdt, cdn, "custom_finished_specification", make_finished_specification(row));
}

function set_requirement_tab(frm, active) {
    frm._dyeing_requirement_tab = active;
    const groups = {
        process: ["custom_process_requirements_tab", "custom_process_requirements"],
        packaging: ["custom_packaging_requirements_tab", "custom_packaging_requirements"],
    };

    Object.entries(groups).forEach(([tab, fieldnames]) => {
        fieldnames.forEach((fieldname) => {
            const field = frm.fields_dict[fieldname];
            if (field && field.$wrapper) field.$wrapper.toggle(tab === active);
        });
    });

    const field = frm.get_field("custom_requirement_tabs_html");
    if (!field || !field.$wrapper) return;

    field.$wrapper.html(`
        <div class="dyeing-requirement-tabs">
            <button type="button" class="btn btn-sm ${active === "process" ? "btn-primary" : "btn-default"}"
                data-dyeing-requirement-tab="process">加工要求</button>
            <button type="button" class="btn btn-sm ${active === "packaging" ? "btn-primary" : "btn-default"}"
                data-dyeing-requirement-tab="packaging">包装要求</button>
        </div>
    `);

    field.$wrapper.off("click.dyeingRequirementTabs").on(
        "click.dyeingRequirementTabs",
        "[data-dyeing-requirement-tab]",
        function () {
            set_requirement_tab(frm, $(this).data("dyeing-requirement-tab"));
        }
    );
}

function configure_item_grid_buttons(frm) {
    const grid = frm.fields_dict.items?.grid;
    if (!grid?.wrapper) return;

    if (!$("#dyeing-hide-add-multiple-rows").length) {
        $("head").append(
            '<style id="dyeing-hide-add-multiple-rows">.grid-add-multiple-rows { display: none !important; }</style>'
        );
    }
    grid.wrapper.find(".grid-add-multiple-rows").remove();

    const add_button = grid.wrapper.find(".grid-add-row");
    add_button.off("click").on("click.dyeingAddOneRow", function (event) {
        event.preventDefault();
        event.stopImmediatePropagation();

        if (grid.wrapper.find(".grid-row-open").length) {
            frappe.msgprint({
                title: "请先关闭编辑行",
                message: "请先点击编辑行右上角的向下箭头关闭当前编辑行，再点击“添加一行”。",
                indicator: "orange",
            });
            return false;
        }

        grid.add_new_row(null, null, true, null, true);
        grid.set_focus_on_row();
        return false;
    });
}

function hide_item_edit_buttons(frm) {
    const grid = frm.fields_dict.items?.grid;
    if (!grid?.wrapper) return;

    grid.wrapper.attr("data-dyeing-item-grid", "1");
    if (!$("#dyeing-hide-item-edit-buttons").length) {
        $("head").append(
            '<style id="dyeing-hide-item-edit-buttons">[data-dyeing-item-grid="1"] .btn-open-row { display: none !important; }</style>'
        );
    }
}
frappe.ui.form.on("Sales Order", {
    refresh(frm) {
        if (!frm.doc.custom_customer_order_no && frm.doc.po_no) {
            frm.set_value("custom_customer_order_no", frm.doc.po_no);
        }
        set_requirement_tab(frm, frm._dyeing_requirement_tab || "process");
        configure_item_grid_buttons(frm);
        hide_item_edit_buttons(frm);
    },
    custom_customer_order_no(frm) {
        if (frm.doc.po_no !== frm.doc.custom_customer_order_no) {
            frm.set_value("po_no", frm.doc.custom_customer_order_no);
        }
    },
    po_no(frm) {
        if (frm.doc.custom_customer_order_no !== frm.doc.po_no) {
            frm.set_value("custom_customer_order_no", frm.doc.po_no);
        }
    },
});

frappe.ui.form.on("Sales Order Item", {
    custom_finished_width(frm, cdt, cdn) {
        update_finished_specification(cdt, cdn);
    },
    custom_finished_gsm(frm, cdt, cdn) {
        update_finished_specification(cdt, cdn);
    },
    custom_finished_gsm_uom(frm, cdt, cdn) {
        update_finished_specification(cdt, cdn);
    },
});
function get_requirement_config(type) {
    return type === "process" ? {
        doctype: "Process Requirement", child_table: "custom_process_requirements", child_field: "process_requirement", name_field: "process_requirement_name", source_name_field: "process_requirement_name"
    } : {
        doctype: "Packaging Requirement", child_table: "custom_packaging_requirements", child_field: "packaging_requirement", name_field: "packaging_requirement_name", source_name_field: "packaging_requirement_name"
    };
}

function add_selected_requirements(frm, type, selections) {
    const config = get_requirement_config(type);
    const existing = new Set((frm.doc[config.child_table] || []).map(row => row[config.child_field]).filter(Boolean));
    [...selections].sort((a, b) => a.localeCompare(b, undefined, {numeric: true})).forEach(name => {
        if (existing.has(name)) return;
        const row = frm.add_child(config.child_table);
        row[config.child_field] = name;
        existing.add(name);
        frappe.db.get_value(config.doctype, name, [config.source_name_field, "description"]).then(r => {
            if (!r.message) return;
            frappe.model.set_value(row.doctype, row.name, config.name_field, r.message[config.source_name_field] || "");
            frappe.model.set_value(row.doctype, row.name, "description", r.message.description || "");
        });
    });
    frm.refresh_field(config.child_table);
}

function open_requirement_multi_select(frm, type) {
    const config = get_requirement_config(type);
    const dialog = new frappe.ui.form.MultiSelectDialog({
        doctype: config.doctype, target: frm, setters: {[config.source_name_field]: ""}, add_filters_group: false,
        action(selections) { add_selected_requirements(frm, type, selections); dialog.dialog.hide(); }
    });
    const configure = () => {
        if (!dialog.$results) return window.setTimeout(configure, 10);
        dialog.page_length = 1000;
        dialog.get_datatable_columns = () => ["name", config.source_name_field];
        const already_selected = new Set((frm.doc[config.child_table] || []).map(row => row[config.child_field]).filter(Boolean));
        const render = dialog.render_result_list.bind(dialog);
        dialog.render_result_list = (results, more, empty) => {
            render([...results].filter(row => !already_selected.has(row.name)).sort((a,b) => a.name.localeCompare(b.name, undefined, {numeric:true})), more, empty);
            dialog.$results.find(".list-item--head .list-item__content:eq(1) span").text("编码");
            dialog.$results.find(".list-item--head .list-item__content:eq(2) span").text("名称");
        };
        dialog.$results.empty().append(dialog.make_list_row());
        dialog.$results.find(".list-item--head .list-item__content:eq(1) span").text("编码");
        dialog.$results.find(".list-item--head .list-item__content:eq(2) span").text("名称");
        dialog.dialog.$wrapper.find(".form-section").first().hide();
        dialog.get_results();
    };
    configure();
}

function set_requirement_tab(frm, active) {
    frm._dyeing_requirement_tab = active;
    const groups = { process: ["custom_process_requirements_tab", "custom_process_requirements"], packaging: ["custom_packaging_requirements_tab", "custom_packaging_requirements"] };
    Object.entries(groups).forEach(([tab, fields]) => fields.forEach(fieldname => {
        const field = frm.fields_dict[fieldname];
        if (field && field.$wrapper) field.$wrapper.toggle(tab === active);
    }));
    const field = frm.get_field("custom_requirement_tabs_html");
    if (!field || !field.$wrapper) return;
    field.$wrapper.html(`<div class="dyeing-requirement-tabs"><button type="button" class="btn btn-sm ${active === "process" ? "btn-primary" : "btn-default"}" data-dyeing-requirement-tab="process">加工要求</button><button type="button" class="btn btn-sm ${active === "packaging" ? "btn-primary" : "btn-default"}" data-dyeing-requirement-tab="packaging">包装要求</button><button type="button" class="btn btn-sm btn-default" data-dyeing-requirement-select="${active}">选择${active === "process" ? "加工要求" : "包装要求"}</button></div>`);
    field.$wrapper.off("click.dyeingRequirementTabs").on("click.dyeingRequirementTabs", "[data-dyeing-requirement-tab]", function(){ set_requirement_tab(frm, $(this).data("dyeing-requirement-tab")); }).on("click.dyeingRequirementTabs", "[data-dyeing-requirement-select]", function(){ open_requirement_multi_select(frm, $(this).data("dyeing-requirement-select")); });
}

function set_color_no_query(frm) {
    frm.set_query("custom_color_no", "items", () => ({
        filters: {
            customer_name: frm.doc.customer || "__no_customer__",
            status: "启用",
        },
    }));
}

frappe.ui.form.on("Sales Order", {
    setup(frm) {
        set_color_no_query(frm);
    },
    customer(frm) {
        set_color_no_query(frm);
    },
    refresh(frm) {
        set_color_no_query(frm);
    },
});

frappe.ui.form.on("Sales Order Item", {
    custom_color_no(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.custom_color_no) {
            frappe.model.set_value(cdt, cdn, "custom_color", "");
            frappe.model.set_value(cdt, cdn, "custom_color_product_name", "");
            return;
        }
        frappe.db.get_value("Color Master", row.custom_color_no, ["color_name", "product_name"]).then((result) => {
            const color = result.message;
            if (!color) return;
            frappe.model.set_value(cdt, cdn, "custom_color", color.color_name || "");
            frappe.model.set_value(cdt, cdn, "custom_color_product_name", color.product_name || "");
        });
    },
});

function hide_sales_order_tax_and_following_sections(frm) {
    const fields = frm.meta.fields || [];
    const taxes_section_index = fields.findIndex((field) => field.fieldname === "taxes_section");
    if (taxes_section_index < 0) return;

    fields.slice(taxes_section_index).forEach((field) => {
        if (field.fieldname && !field.custom) {
            frm.toggle_display(field.fieldname, false);
        }
    });
}

frappe.ui.form.on("Sales Order", {
    refresh(frm) {
        hide_sales_order_tax_and_following_sections(frm);
    },
});

function configure_sales_order_item_amount_display(frm) {
    const grid = frm.fields_dict.items?.grid;
    if (!grid) return;

    [
        ["rate", "单价"],
        ["amount", "金额"],
    ].forEach(([fieldname, label]) => {
        const field = grid.get_field(fieldname);
        if (!field || !field.df) return;
        field.df.label = label;
        field.df.formatter = (value, df, options, doc) =>
            frappe.form.formatters.Float(value, { ...df, fieldtype: "Float", options: "" }, options, doc);
    });
    grid.refresh();
}

frappe.ui.form.on("Sales Order", {
    refresh(frm) {
        configure_sales_order_item_amount_display(frm);
    },
});

function configure_sales_order_item_amount_display(frm) {
    const grid = frm.fields_dict.items?.grid;
    if (!grid) return;

    [
        ["rate", "单价"],
        ["amount", "金额"],
    ].forEach(([fieldname, label]) => {
        const formatter = (value, df, options, doc) =>
            frappe.form.formatters.Float(value, { ...df, fieldtype: "Float", options: "" }, options, doc);
        const docfield = frappe.meta.get_docfield("Sales Order Item", fieldname, frm.doc.name);
        if (docfield) {
            docfield.label = label;
            docfield.formatter = formatter;
        }
        grid.update_docfield_property(fieldname, "label", label);
        grid.update_docfield_property(fieldname, "formatter", formatter);
    });
    grid.refresh();
}
