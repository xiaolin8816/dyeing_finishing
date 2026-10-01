import frappe


TEMPLATES = {
    "染色工艺参数": ("染色", [
        ("染色", "浴比", "", ""), ("染色", "起始温度", "℃", ""), ("染色", "目标温度", "℃", ""),
        ("染色", "升温速度", "℃/分钟", ""), ("染色", "保温时间", "分钟", ""), ("染色", "pH 值", "", ""),
        ("染色", "加料方式", "", "一次加入/分批加入/连续加入"), ("染色", "加料时间", "分钟", ""),
        ("染色", "分批次数", "次", ""), ("染色", "降温方式", "", "自然降温/冷水降温/排液降温"),
    ]),
    "单定工艺参数": ("单定", [
        ("定型整理", "定型温度", "℃", ""), ("定型整理", "定型时间或车速", "", ""),
        ("定型整理", "门幅", "", ""), ("定型整理", "超喂", "%", ""), ("定型整理", "张力", "", ""),
    ]),
    "前定染色工艺参数": ("前定染色", [
        ("定型整理", "前定温度", "℃", ""), ("定型整理", "前定时间或车速", "", ""),
        ("染色", "染色温度", "℃", ""), ("染色", "保温时间", "分钟", ""), ("染色", "张力", "", ""),
    ]),
    "定边染色工艺参数": ("定边染色", [
        ("定型整理", "定边宽度", "", ""), ("定型整理", "温度", "℃", ""),
        ("定型整理", "车速", "", ""), ("定型整理", "超喂", "%", ""),
        ("定型整理", "张力", "", ""), ("染色", "染色温度", "℃", ""),
    ]),
    "精练染色工艺参数": ("精练染色", [
        ("前处理", "精练温度", "℃", ""), ("前处理", "精练时间", "分钟", ""),
        ("前处理", "pH 值", "", ""), ("前处理", "洗水次数", "次", ""),
        ("染色", "浴比", "", ""), ("染色", "染色温度", "℃", ""),
        ("染色", "保温时间", "分钟", ""),
    ]),
}


def execute():
    for template_name, (process_type, parameters) in TEMPLATES.items():
        if frappe.db.exists("Process Parameter Template", {"template_name": template_name}):
            continue
        template = frappe.get_doc({
            "doctype": "Process Parameter Template",
            "template_name": template_name,
            "process_type": process_type,
            "status": "启用",
        })
        for index, (stage, parameter_name, unit, instruction) in enumerate(parameters, start=1):
            template.append("parameter_items", {
                "sequence_no": index,
                "process_stage": stage,
                "parameter_name": parameter_name,
                "unit": unit,
                "default_value": "",
                "is_required": 0,
                "instruction": instruction,
            })
        template.insert(ignore_permissions=True)
