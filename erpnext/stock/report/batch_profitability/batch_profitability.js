// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Batch Profitability"] = {
	"filters": [
		{
			fieldname: "batch_no",
			label: __("Batch"),
			fieldtype: "Link",
			reqd: 1,
			options:"Batch",
		},
	]
};
