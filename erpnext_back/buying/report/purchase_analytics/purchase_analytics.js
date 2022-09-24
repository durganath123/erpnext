// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Purchase Analytics"] = {
	"filters": [
		{
			fieldname: "tree_type",
			label: __("Tree Type"),
			fieldtype: "Select",
			options: ["Supplier Group","Supplier","Item Group","Item","Brand"],
			default: "Item",
			reqd: 1
		},
		{
			fieldname: "doctype",
			label: __("Based On"),
			fieldtype: "Select",
			options: ["Purchase Order","Purchase Receipt","Purchase Invoice"],
			default: "Purchase Receipt",
			reqd: 1
		},
		{
			fieldname: "value_field",
			label: __("Amount Or Qty"),
			fieldtype: "Select",
			options: ["Net Amount", "Amount", "Stock Qty", "Contents Qty", "Transaction Qty"],
			default: "Stock Qty",
			reqd: 1
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.defaults.get_user_default("year_start_date"),
			reqd: 1
		},
		{
			fieldname:"to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1
		},
		{
			fieldname: "range",
			label: __("Range"),
			fieldtype: "Select",
			options: [
				{ "value": "Weekly", "label": __("Weekly") },
				{ "value": "Monthly", "label": __("Monthly") },
				{ "value": "Quarterly", "label": __("Quarterly") },
				{ "value": "Yearly", "label": __("Yearly") }
			],
			default: "Weekly",
			reqd: 1
		},
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier"
		},
		{
			fieldname: "supplier_group",
			label: __("Supplier Group"),
			fieldtype: "Link",
			options: "Supplier Group"
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item"
		},
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group"
		},
		{
			fieldname: "brand",
			label: __("Brand"),
			fieldtype: "Link",
			options: "Brand"
		},
		{
			fieldname: "cost_center",
			label: __("Cost Center"),
			fieldtype: "Link",
			options: "Cost Center"
		},
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "Link",
			options: "Project"
		},
	],
	after_datatable_render: function(datatable_obj) {
		const checkbox = $(datatable_obj.wrapper).find(".dt-row-0").find('input[type=checkbox]');
		if(!checkbox.prop("checked")) {
			checkbox.click();
		}
	},
	get_datatable_options(options) {
		return Object.assign(options, {
			checkboxColumn: true,
			events: {
				onCheckRow: function(data) {
					let row_name = data[2].content;
					let period_columns = [];
					$.each(frappe.query_report.columns || [], function(i, column) {
						if (column.period_column) {
							period_columns.push(i+2);
						}
					});

					let row_values = period_columns.map(i => data[i].content);
					let entry = {
						'name':row_name,
						'values':row_values
					};

					let raw_data = frappe.query_report.chart.data;
					let new_datasets = raw_data.datasets;

					let found = false;

					for(var i=0; i < new_datasets.length;i++){
						if(new_datasets[i].name == row_name){
							found = true;
							new_datasets.splice(i,1);
							break;
						}
					}

					if(!found){
						new_datasets.push(entry);
					}

					let new_data = {
						labels: raw_data.labels,
						datasets: new_datasets
					};

					setTimeout(() => {
						frappe.query_report.chart.update(new_data)
					}, 500);


					setTimeout(() => {
						frappe.query_report.chart.draw(true);
					}, 1000);

					frappe.query_report.raw_chart_data = new_data;
				},
			}
		});
	},
	formatter: function(value, row, column, data, default_formatter) {
		var options = {
			link_target: "_blank"
		};

		if (data && column.start_date && column.end_date) {
			var dt = frappe.query_report.get_filter_value('doctype');
			var link = `#List/${encodeURIComponent(dt)}/Report`;
			var filters = {
				posting_date: `["Between", ["${column.start_date}", "${column.end_date}"]]`,
				docstatus: 1
			};

			$.each(['item_code', 'customer', 'customer_group', 'item_group', 'brand', 'territory', 'sales_person', 'project'], function (i, fieldname) {
				filters[fieldname] = frappe.query_report.get_filter_value(fieldname);
			});

			var entity_type = frappe.query_report.get_filter_value('tree_type');
			var entity = data.entity;
			if (entity_type && entity) {
				filters[frappe.model.scrub(entity_type)] = entity;
			}

			var filter_list = [];
			$.each(filters || {}, function (k, v) {
				if (v) {
					filter_list.push(`${encodeURIComponent(k)}=${encodeURIComponent(v)}`);
				}
			});
			var args = filter_list.join("&");
			if (args) {
				options.link_href = link + "?" + args;
			}
		}
		return default_formatter(value, row, column, data, options);
	}
}
