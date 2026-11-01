const ENERGY_METER_METHOD = "dyeing_finishing.dyeing_finishing.doctype.dyeing_energy_meter.dyeing_energy_meter.";
const ENERGY_READING_METHOD = "dyeing_finishing.dyeing_finishing.doctype.dyeing_energy_meter_reading.dyeing_energy_meter_reading.";

function apply_energy_reading_layout(frm) {
    frm.get_field("document_section")?.wrapper?.addClass("dyeing-responsive-form-grid");
    const $head = frm.get_field("items_section")?.wrapper?.find(".section-head").first();
    frm.get_field("items")?.$wrapper?.find(".grid-field > .control-label").first().hide();
    if (!$head?.length) return;
    $head.find(".dyeing-select-energy-meters").remove();
    if (frm.doc.docstatus !== 0 || frm.get_field("items")?.get_status() !== "Write") return;
    $head.css({display: "flex", alignItems: "center", flexWrap: "wrap", columnGap: "12px"});
    $("<button>", {
        type: "button",
        class: "btn btn-xs btn-secondary dyeing-select-energy-meters",
        text: "选择表计",
    }).on("click", () => select_energy_meters(frm)).appendTo($head);
}

async function fetch_meter_contexts(frm, names) {
    if (!frm.doc.reading_time) {
        frappe.msgprint("请先填写抄表时间。");
        return [];
    }
    const response = await frappe.call({
        method: ENERGY_READING_METHOD + "get_meter_contexts",
        args: {
            meters: names,
            reading_time: frm.doc.reading_time,
            company: frm.doc.company || "",
        },
    });
    return response.message || [];
}

async function select_energy_meters(frm) {
    await frappe.model.with_doctype("Dyeing Energy Meter");
    const existing = new Set((frm.doc.items || []).map((row) => row.meter));
    const dialog = new frappe.ui.form.MultiSelectDialog({
        doctype: "Dyeing Energy Meter",
        target: frm,
        setters: {},
        add_filters_group: false,
        size: "large",
        columns: ["表计编码", "表计名称", "能源类型", "计量范围", "单位"],
        primary_action_label: "加入抄表明细",
        get_query() {
            return {
                query: ENERGY_METER_METHOD + "search_energy_meters",
                filters: {company: frm.doc.company || "__no_company__"},
            };
        },
        async action(selections) {
            const names = selections.filter((name) => !existing.has(name));
            if (!names.length) {
                frappe.show_alert({message: "所选表计已在明细中", indicator: "orange"});
                return;
            }
            const contexts = await fetch_meter_contexts(frm, names);
            if (contexts.length !== names.length) return;
            contexts.forEach((values) => Object.assign(frm.add_child("items"), values));
            frm.refresh_field("items");
            await frm.set_value("meter_count", (frm.doc.items || []).length);
            dialog.dialog.hide();
        },
    });
    dialog.page_length = 1000;
    dialog.dialog.set_title("选择能源表计");
    dialog.dialog.set_df_property("search_term", "label", "表计查询");
    dialog.dialog.set_df_property("search_term", "placeholder", "输入编码、名称或能源类型");
    dialog.dialog.get_secondary_btn().hide();
    dialog.get_results();
}

async function refresh_meter_rows(frm) {
    const rows = (frm.doc.items || []).filter((row) => row.meter);
    if (!rows.length) return;
    const contexts = await fetch_meter_contexts(frm, rows.map((row) => row.meter));
    const by_meter = new Map(contexts.map((item) => [item.meter, item]));
    rows.forEach((row) => {
        if (!by_meter.has(row.meter)) return;
        Object.assign(row, by_meter.get(row.meter));
        update_consumption(row);
    });
    frm.refresh_field("items");
    frm.dirty();
}

function update_consumption(row) {
    if (row.current_reading === null || row.current_reading === undefined || row.current_reading === "") {
        row.consumption = 0;
        return;
    }
    const previous = flt(row.previous_reading);
    const current = flt(row.current_reading);
    const capacity = flt(row.rollover_capacity);
    const multiplier = flt(row.multiplier);
    const difference = row.reading_method === "翻表"
        ? (capacity > 0 && current < previous ? capacity - previous + current : 0)
        : (current >= previous ? current - previous : 0);
    row.consumption = flt(difference * multiplier, 6);
}

frappe.ui.form.on("Dyeing Energy Meter Reading", {
    setup(frm) {
        frm.set_df_property("items", "cannot_add_rows", true);
        if (frm.is_new() && !frm.doc.company) {
            frm.set_value("company", frappe.defaults.get_user_default("Company") || frappe.boot.sysdefaults.company);
        }
    },
    refresh(frm) {
        frm.set_df_property("items", "cannot_add_rows", true);
        apply_energy_reading_layout(frm);
    },
    reading_time(frm) {
        return refresh_meter_rows(frm);
    },
});

frappe.ui.form.on("Dyeing Energy Meter Reading Item", {
    items_add(frm) {
        frm.set_value("meter_count", (frm.doc.items || []).length);
    },
    items_remove(frm) {
        frm.set_value("meter_count", (frm.doc.items || []).length);
    },
    current_reading(frm, cdt, cdn) {
        update_consumption(locals[cdt][cdn]);
        frm.refresh_field("items");
    },
    reading_method(frm, cdt, cdn) {
        update_consumption(locals[cdt][cdn]);
        frm.refresh_field("items");
    },
});
