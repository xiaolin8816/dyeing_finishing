dyeing_finishing_report_layout.register({
	report_name: "Grey Fabric Inventory Count Difference",
	filters: [
		{fieldname:"from_date", label:__("开始日期"), fieldtype:"Date", default:frappe.datetime.add_months(frappe.datetime.get_today(), -1)},
		{fieldname:"to_date", label:__("结束日期"), fieldtype:"Date", default:frappe.datetime.get_today()},
		{fieldname:"inventory_count", label:__("胚布盘点表"), fieldtype:"Link", options:"Grey Fabric Inventory Count"},
		{fieldname:"warehouse", label:__("盘点仓库/货位"), fieldtype:"Link", options:"Warehouse"},
		{fieldname:"customer", label:__("客户"), fieldtype:"Link", options:"Customer"},
		{fieldname:"status", label:__("状态"), fieldtype:"Select", options:"\n草稿\n待审核\n已审核\n已驳回\n已取消", default:"已审核"},
		{fieldname:"only_difference", label:__("仅显示差异"), fieldtype:"Check", default:1},
	],
});
