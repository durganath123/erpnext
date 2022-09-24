// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("erpnext.stock");

erpnext.stock.StockController = frappe.ui.form.Controller.extend({
	onload: function() {
		// warehouse query if company
		if (this.frm.fields_dict.company) {
			this.setup_warehouse_query();
		}
	},

	setup_warehouse_query: function() {
		var me = this;
		erpnext.queries.setup_queries(this.frm, "Warehouse", function() {
			return erpnext.queries.warehouse(me.frm.doc);
		});
	},

	setup_posting_date_time_check: function() {
		// make posting date default and read only unless explictly checked
		frappe.ui.form.on(this.frm.doctype, 'set_posting_date_and_time_read_only', function(frm) {
			if(frm.doc.docstatus == 0 && frm.doc.set_posting_time) {
				frm.set_df_property('posting_date', 'read_only', 0);
				frm.set_df_property('posting_time', 'read_only', 0);
			} else {
				frm.set_df_property('posting_date', 'read_only', 1);
				frm.set_df_property('posting_time', 'read_only', 1);
			}
		})

		frappe.ui.form.on(this.frm.doctype, 'set_posting_time', function(frm) {
			frm.trigger('set_posting_date_and_time_read_only');
		});

		frappe.ui.form.on(this.frm.doctype, 'refresh', function(frm) {
			// set default posting date / time
			if(frm.doc.docstatus==0) {
				if(!frm.doc.posting_date) {
					frm.set_value('posting_date', frappe.datetime.nowdate());
				}
				if(!frm.doc.posting_time) {
					frm.set_value('posting_time', frappe.datetime.now_time());
				}
				frm.trigger('set_posting_date_and_time_read_only');
			}
		});
	},

	show_stock_ledger: function() {
		var me = this;
		if(this.frm.doc.docstatus===1) {
			cur_frm.add_custom_button(__("Stock Ledger"), function() {
				frappe.route_options = {
					voucher_no: me.frm.doc.name,
					from_date: me.frm.doc.posting_date,
					to_date: me.frm.doc.posting_date,
					company: me.frm.doc.company
				};
				frappe.set_route("query-report", "Stock Ledger");
			}, __("View"));
		}

	},

	show_general_ledger: function() {
		var me = this;
		if(this.frm.doc.docstatus===1) {
			cur_frm.add_custom_button(__('Accounting Ledger'), function() {
				frappe.route_options = {
					voucher_no: me.frm.doc.name,
					from_date: me.frm.doc.posting_date,
					to_date: me.frm.doc.posting_date,
					company: me.frm.doc.company,
					group_by: "Group by Voucher (Consolidated)"
				};
				frappe.set_route("query-report", "General Ledger");
			}, __("View"));
		}
	},

	build_print_item_labels_dialog(get_data, table_fields, print_format_filter, show_callback) {
		const me = this;
		frappe.model.with_doctype("Item", () => {
			const meta = frappe.get_meta("Item");

			me.item_print_dialog_data = [];
			if (get_data) {
				me.item_print_dialog_data = get_data();
			}

			let available_print_formats = meta.__print_formats.filter(d => d.raw_printing);
			if (print_format_filter) {
				available_print_formats = available_print_formats.filter(print_format_filter);
			}
			available_print_formats = available_print_formats.map(d => d.name);

			let default_print_format = available_print_formats.includes(meta.default_print_format) ? meta.default_print_format : "";
			if (!default_print_format && available_print_formats.length) {
				default_print_format = available_print_formats[0];
			}

			let fields = [
				{fieldtype: "Select", fieldname: "print_format", label: __("Print Format"), "reqd": 1,
					"default": default_print_format,
					"options": available_print_formats},
				{fieldtype: 'Section Break'}
			];
			table_fields = Object.assign({
				label: __("Labels"),
				fieldname: "item_args",
				fieldtype: "Table",
				data: me.item_print_dialog_data,
				get_data: () => me.item_print_dialog_data,
				in_place_edit: true,
				cannot_add_rows: true
			}, table_fields);
			fields.push(table_fields);

			var dialog = new frappe.ui.Dialog({
				title: __("Item Label Print"),
				fields: fields
			});
			dialog.set_primary_action(__("Print"), function() {
				let item_args = dialog.get_values()["item_args"];
				let print_format = dialog.get_value('print_format');
				let printer = me.get_mapped_printer("Item", print_format);

				if (printer) {
					me.print_item_labels(item_args, print_format, printer);
				} else {
					frappe.ui.form.qz_get_printer_list().then((data) => {
						let printer_dialog = new frappe.ui.Dialog({
							title: __("Select Printer"),
							fields: [{fieldtype: "Select", fieldname: "printer", label: __("Printer"), "reqd": 1,
								"options": data || ""
							}]
						});
						printer_dialog.set_primary_action(__("Print"), function () {
							printer = printer_dialog.get_value('printer');

							if (printer) {
								// set printer mapping
								let print_format_printer_map = me.frm.print_preview.get_print_format_printer_map();
								if (!print_format_printer_map['Item']) {
									print_format_printer_map['Item'] = [];
								}
								print_format_printer_map['Item'] = print_format_printer_map['Item'].filter(d => d.printer != printer && d.print_format != print_format);
								print_format_printer_map['Item'].push({printer: printer, print_format: print_format});
								localStorage.print_format_printer_map = JSON.stringify(print_format_printer_map);

								// print
								me.print_item_labels(item_args, print_format, printer);
							}
							printer_dialog.hide();
						});
						printer_dialog.show();
					});
				}

				dialog.hide();
			});

			if (show_callback) {
				show_callback(dialog);
			}
			dialog.show({backdrop: 'static', keyboard: false});
		});
	},

	print_item_labels: function(item_args, print_format, printer) {
		frappe.call({
			method: "erpnext.stock.doctype.item.item.get_item_print_raw_commands",
			args: {
				"item_args": item_args,
				"print_format": print_format
			},
			callback: function (r) {
				if (r.message && r.message.length) {
					frappe.ui.form.qz_connect().then(function () {
						let config = qz.configs.create(printer);
						return qz.print(config, r.message);
					}).then(frappe.ui.form.qz_success).catch((err) => {
						frappe.ui.form.qz_fail(err);
					});
				}
			}
		});
	},

	get_mapped_printer: function(doctype, print_format) {
		let printers = [];
		let print_format_printer_map = this.frm.print_preview.get_print_format_printer_map();
		if (print_format_printer_map["Batch"]) {
			printers = print_format_printer_map["Batch"].filter(
				(printer_map) => printer_map.print_format == print_format);
		}

		return printers.length ? printers[0].printer : "";
	},
});
