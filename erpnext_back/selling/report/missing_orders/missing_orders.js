// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Missing Orders"] = {
	"filters": [
		{
			"fieldname":"delivery_date",
			"label": __("Delivery Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname":"doctype",
			"label": __("Doctype"),
			"fieldtype": "Select",
			"default": "Sales Order",
			"options": "Sales Order\nSales Invoice"
		},
		{
			"fieldname":"enable_disable",
			"label": __("Enabled/Disabled"),
			"fieldtype": "Select",
			"default": "Enabled Customers",
			"options": "Enabled Customers\nDisabled Customers\nAll Customers"
		}
	]
}
