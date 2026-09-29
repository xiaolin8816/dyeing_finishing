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