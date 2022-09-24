// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.provide("erpnext.selling");

erpnext.selling.QtyAdjustController = frappe.ui.form.Controller.extend({
	setup: function() {
		var me = this;
		$(this.frm.wrapper).on('grid-row-render', function(e, grid_row) {
			me.set_row_editable(grid_row);


			$(grid_row.wrapper).off('click').on('click', function() {
				me.set_row_editable(grid_row);
			});
			$(grid_row.wrapper).off('keydown', 'input').on('keydown', 'input', function(e) {
				me.set_row_editable(grid_row, e);
			});
			$(grid_row.wrapper).off('mouseover', 'input').on('mouseover', 'input', function(e) {
				me.set_row_editable(grid_row, e);
			});
		});

		this.frm.doc.from_date = get_url_arg("from_date");
		this.frm.doc.to_date = get_url_arg("to_date");
		this.frm.doc.item_code = get_url_arg("item_code");
		this.frm.trigger("item_code");
	},

	refresh: function() {
		this.frm.disable_save();
		this.frm.add_custom_button(__('Qty Adjust Report'), function() {
			frappe.set_route('query-report', 'Qty Adjust');
		});
	},

	onload: function() {
		this.set_po_qty_labels();
	},

	sales_orders_on_form_rendered: function() {
		this.set_row_editable(this.frm.open_grid_row());
	},

	onload_post_render: function() {
		var me = this;

		me.frm.fields_dict.qty_adjust_sales_orders.$input.addClass("btn-primary");
		$(".grid-footer", me.frm.fields_dict.sales_orders.$wrapper).hide().addClass("hidden");

		me.frm.fields_dict.sales_orders.grid.wrapper.on('click', '.grid-row-check', function(e) {
			me.calculate_totals();
		});
	},

	is_row_editable: function(row) {
		return Boolean(row.doc_status === 0 && row.dt === "Sales Order");
	},

	set_row_editable: function(grid_row, e) {
		if(grid_row) {
			var editable = this.is_row_editable(grid_row.doc);

			if (!editable) {
				$("input", grid_row.wrapper).prop('disabled', !editable);

				if (this.frm.open_grid_row()) {
					$("input", this.frm.open_grid_row().grid_form.wrapper).prop('disabled', !editable);
				}
			}
			$("input, .static-area, a", grid_row.wrapper).css("color", editable ? "inherit" : "red");

			if (e && !editable) {
				e.preventDefault();
			}
		}
	},

	from_date: function() {
		this.set_po_qty_labels();
		this.get_item_custom_projected_qty();
		this.get_sales_orders_for_qty_adjust();
	},

	to_date: function() {
		this.get_sales_orders_for_qty_adjust();
	},

	item_code: function() {
		this.get_item_name();
		this.get_item_custom_projected_qty();
		this.get_sales_orders_for_qty_adjust();
	},

	sort_by: function () {
		this.get_sales_orders_for_qty_adjust();
	},

	allocated_qty: function() {
		this.calculate_totals();
	},

	back_order_qty: function() {
		this.calculate_totals();
	},

	sales_orders_remove: function() {
		this.calculate_totals();
	},

	new_item_code: function(frm, cdt, cdn) {
		var me = this;
		var grid_row = this.frm.fields_dict['sales_orders'].grid.grid_rows_by_docname[cdn];
		if (grid_row && grid_row.doc.__checked) {
			var checked_rows = this.frm.fields_dict['sales_orders'].grid.grid_rows
				.filter(row => row.doc.__checked && row.doc.name != cdn);

			$.each(checked_rows || [], function(i, d) {
				if (me.is_row_editable(d.doc)) {
					d.doc.new_item_code = grid_row.doc.new_item_code;
				}
			});

			this.frm.refresh_field("sales_orders");
		}
	},

	get_item_name: function() {
		var me = this;

		if (me.frm.doc.item_code) {
			return frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Item",
					filters: {name: me.frm.doc.item_code},
					fieldname: "item_name"
				},
				callback: function(r) {
					if(r.message) {
						me.frm.set_value("item_name", r.message.item_name);
					}
				}
			});
		} else {
			me.frm.set_value("item_name", "");
		}
	},

	set_po_qty_labels: function() {
		var from_date = this.frm.doc.from_date || frappe.datetime.now_date();
		for (var i = 0; i < 5; ++i) {
			var date = new frappe.datetime.datetime(frappe.datetime.add_days(from_date, i));
			var day = date.format("ddd");
			this.frm.fields_dict["po_day_"+(i+1)].set_label("PO " + day);
			// this.frm.fields_dict["so_day_"+(i+1)].set_label("SO " + day);
		}
	},

	get_item_custom_projected_qty: function() {
		var me = this;

		if (me.frm.doc.from_date && me.frm.doc.item_code) {
			return this.frm.call({
				method: "erpnext.stock.get_item_details.get_item_custom_projected_qty",
				freeze: true,
				args: {
					date: me.frm.doc.from_date,
					item_codes: [me.frm.doc.item_code]
				},
				callback: function(r) {
					if(!r.exc) {
						if(r.message.hasOwnProperty(me.frm.doc.item_code)) {
							var res = r.message[me.frm.doc.item_code];
							me.frm.doc['actual_qty'] = res['actual_qty'];
							me.frm.doc['projected_qty'] = res['projected_qty'];
							for(var i = 0; i < 5; ++i) {
								me.frm.doc['po_day_' + (i + 1)] = res['po_day_' + (i + 1)];
								me.frm.doc['so_day_' + (i + 1)] = res['so_day_' + (i + 1)];
							}
						} else {
							me.frm.doc['actual_qty'] = 0;
							me.frm.doc['projected_qty'] = 0;
							for(var i = 0; i < 5; ++i) {
								me.frm.doc['po_day_' + (i + 1)] = 0;
								me.frm.doc['so_day_' + (i + 1)] = 0;
							}
						}

						me.frm.refresh_fields();
					}
				}
			});
		}
	},

	get_sales_orders_for_qty_adjust: function() {
		var me = this;

		if (me.frm.doc.from_date && me.frm.doc.item_code) {
			return this.frm.call({
				method: "erpnext.selling.doctype.qty_adjust.qty_adjust.get_sales_orders_for_qty_adjust",
				freeze: true,
				args: {
					from_date: me.frm.doc.from_date,
					to_date: me.frm.doc.to_date,
					item_code: me.frm.doc.item_code,
					sort_by: me.frm.doc.sort_by
				},
				callback: function(r) {
					if(!r.exc) {
						me.frm.doc.sales_orders = [];
						$.each(r.message || [], function(i, d) {
							var row = me.frm.add_child("sales_orders");
							Object.assign(row, d);
							row.allocated_qty = row.qty;
						});

						me.calculate_totals();
					}
				}
			});
		}
	},

	calculate_totals: function() {
		var me = this;

		var totals = {
			total_qty: 0, total_allocated_qty: 0, total_back_order_qty: 0, total_difference: 0,
			selected_qty: 0, selected_allocated_qty: 0, selected_back_order_qty: 0, selected_difference: 0,
		};

		var has_checked = false;
		me.frm.refresh_field("sales_orders");
		$.each(me.frm.fields_dict.sales_orders.grid.grid_rows || [], function(i, d) {
			d.doc.difference = flt(d.doc.allocated_qty) - flt(d.doc.qty);
			$.each(['qty', 'allocated_qty', 'back_order_qty', 'difference'], function(j, f) {
				d.doc[f] = flt(d.doc[f], precision(f, d.doc));
				totals['total_' + f] += flt(d.doc[f]);

				if (d.doc.__checked) {
					has_checked = true;
					totals['selected_' + f] += flt(d.doc[f]);
				}
			});
		});

		Object.assign(me.frm.doc, totals);

		me.frm.refresh_fields();
	},

	qty_adjust_sales_orders: function() {
		var me = this;

		if (me.frm.doc.sales_orders.length) {
			return me.frm.call({
				method: "qty_adjust_sales_orders",
				doc: me.frm.doc,
				args: {
					checked_rows: me.frm.fields_dict.sales_orders.grid.grid_rows.filter(row => row.doc.__checked).map(row => row.doc.name)
				},
				freeze: true,
				callback: function(r) {
					if(!r.exc) {
						me.get_sales_orders_for_qty_adjust();
					}
				}
			});
		}
	}
});

$.extend(cur_frm.cscript, new erpnext.selling.QtyAdjustController({frm: cur_frm}));
