import json

import frappe


def _link(label, link_type, link_to, icon="list"):
	item = {"child": 1, "icon": icon, "label": label, "link_type": link_type, "link_to": link_to, "type": "Link"}
	if link_to == "Item" and label == "染料物料档案":
		item["filters"] = json.dumps([["Item", "item_group", "in", ["染料", "助剂"]]], ensure_ascii=False)
	elif link_to == "Item" and label == "成品物料档案":
		item["filters"] = json.dumps([["Item", "item_group", "=", "成品"]], ensure_ascii=False)
	return item


def _section(label, icon, workspace, links):
    return [
        {"child": 0, "collapsible": 1, "icon": icon, "indent": 0, "keep_closed": 1, "label": label, "show_arrow": 0, "type": "Section Break"},
        _link(f"{label}首页", "Workspace", workspace, "home"),
        *[_link(*item) for item in links],
    ]


ITEMS = [
    {"child": 0, "icon": "home", "label": "印染整理首页", "link_type": "Workspace", "link_to": "印染整理", "type": "Link"},
    *_section("基础资料", "settings", "印染基础资料", [
        ("客户资料", "DocType", "Customer"), ("供应商资料", "DocType", "Supplier"),
        ("员工资料", "DocType", "Employee"), ("仓库资料", "DocType", "Warehouse"),
        ("计量单位", "DocType", "UOM"), ("物料组", "DocType", "Item Group"),
        ("加工要求", "DocType", "Process Requirement"), ("包装要求", "DocType", "Packaging Requirement"),
        ("生产工序", "DocType", "Production Operation"), ("工艺参数模板", "DocType", "Process Parameter Template"),
        ("胚布档案", "DocType", "Grey Fabric Master"), ("生产工段", "DocType", "Production Work Center"),
        ("生产机台", "DocType", "Production Resource"), ("生产班次", "DocType", "Production Shift"),
    ]),
    *_section("配方与工艺", "template", "配方与工艺", [
        ("色号档案", "DocType", "Color Master"), ("化验室配方档案", "DocType", "Laboratory Recipe"),
    ]),
    *_section("胚布管理", "stock", "胚布管理", [
        ("客户胚布入库", "DocType", "Customer Grey Fabric Receipt"), ("胚布出库单", "DocType", "Grey Fabric Issue"),
        ("胚布库存", "Report", "Grey Fabric Stock"), ("胚布过户单", "DocType", "Grey Fabric Customer Transfer"),
        ("客户胚布退货单", "DocType", "Customer Grey Fabric Return"),
        ("生产中转仓库存", "Report", "Production Transit Warehouse Stock"),
    ]),
    *_section("生产管理", "manufacturing", "生产管理", [
        ("染整销售订单", "DocType", "Dyeing Sales Order"), ("生产流转卡", "Page", "production-flow-card-normal"),
        ("生产流转卡回修", "Page", "production-flow-card-rework"), ("生产排程操作台", "Page", "production-schedule-board"),
        ("生产进度大屏", "Page", "production-progress-screen"), ("生产工序扫码报工", "Page", "shop-floor-reporting"),
        ("生产流转卡进度查询", "Report", "Production Flow Card Progress Query"),
        ("生产工序报工记录", "DocType", "Production Operation Report"),
        ("员工工序设置", "DocType", "Employee Operation Permission"),
        ("设备停机记录", "DocType", "Machine Production Calendar"),
        ("排程记录", "DocType", "Dyeing Production Schedule"),
        ("现场染色料单", "DocType", "Site Dyeing Material Sheet"),
    ]),
    *_section("染料管理", "dye", "染料管理", [
        ("染料采购入库单", "DocType", "Purchase Receipt"), ("现场染色领料单", "DocType", "Site Dyeing Material Issue"),
        ("染料其他出库单", "DocType", "Dye Material Other Issue"), ("染料退货单", "DocType", "Dye Material Return"),
        ("染料退货记录", "Report", "Dye Material Return Register"), ("染料库存", "Report", "Dye Material Stock"),
        ("染料物料档案", "DocType", "Item"),
    ]),
    *_section("成品管理", "stock", "成品管理", [
        ("成品空白标签打印单", "DocType", "Finished Product Blank Label"),
        ("成品包装入库单", "DocType", "Finished Product Packing Receipt"), ("成品出库单", "DocType", "Finished Product Delivery"),
        ("成品转客户单", "DocType", "Finished Product Customer Transfer"), ("成品退货处理单", "DocType", "Finished Product Return"),
        ("成品物料档案", "DocType", "Item"), ("成品库存查询", "Report", "Finished Product Stock"),
        ("成品退货库存查询", "Report", "Finished Product Return Stock"),
        ("成品退货转胚布仓", "DocType", "Finished Product Return to Grey Fabric"),
        ("成品库存转胚布仓", "DocType", "Finished Product to Grey Fabric"),
    ]),
    *_section("系统管理", "settings", "系统管理", [
        ("公司资料设置", "DocType", "Company"), ("公司名称变更", "DocType", "Company Name Change"),
        ("系统设置", "DocType", "Dyeing System Settings"),
        ("授权管理", "DocType", "Dyeing Finishing License"),
        ("报表设计中心", "Page", "dyeing-print-template-manager"),
        ("纸张规格", "DocType", "Dyeing Paper Format"),
        ("报表引擎诊断", "Page", "dyeing-report-engine-diagnostics"),
    ]),
]


def execute():
    if not frappe.db.exists("Workspace Sidebar", "印染整理"):
        return
    sidebar = frappe.get_doc("Workspace Sidebar", "印染整理")
    sidebar.set("items", ITEMS)
    sidebar.save(ignore_permissions=True)
