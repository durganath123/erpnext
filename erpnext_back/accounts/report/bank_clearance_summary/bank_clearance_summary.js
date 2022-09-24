// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.query_reports["Bank Clearance Summary"] = {
	"filters": [
		{
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": "",
			"width": "80"
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": ""
		},
		{
			"fieldname":"account",
			"label": __("Bank Account"),
			"fieldtype": "Link",
			"options": "Account",
			"reqd": 1,
			"default": frappe.defaults.get_user_default("Company")?
				locals[":Company"][frappe.defaults.get_user_default("Company")]["default_bank_account"]: "",
			"get_query": function() {
				return {
					"query": "erpnext.controllers.queries.get_account_list",
					"filters": [
						['Account', 'account_type', 'in', 'Bank, Cash'],
						['Account', 'is_group', '=', 0],
					]
				}
			}
		},
		{
			"fieldname":"clearance_date",
			"label": __("Clearance Date"),
			"fieldtype": "Date",
			"default": ""
		}
	]
}
