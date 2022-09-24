// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.provide("erpnext.selling");

erpnext.selling.QtyAdjustStockCountController = frappe.ui.form.Controller.extend({
	setup: function() {
		this.remove_sidebar();
		this.frm.doc.from_date = get_url_arg("from_date");
		this.frm.doc.to_date = get_url_arg("to_date");

		if (!this.frm.doc.from_date) {
			this.frm.doc.from_date = frappe.datetime.get_today();
		}
		if (!this.frm.doc.to_date) {
			this.frm.doc.to_date = frappe.datetime.add_days(frappe.datetime.get_today(), 1);
		}
	},

	onload: function () {
		if (this.frm.doc.__onload && this.frm.doc.__onload.has_local_changes) {
			this.frm.dirty();
		}
		this.setup_realtime();
	},

	refresh: function() {
		this.frm.add_custom_button(__('Qty Adjust Report'), function() {
			frappe.set_route('query-report', 'Qty Adjust');
		});
		this.refresh_qty_warning_color();
	},

	get_items: function () {
		var me = this;
		return me.frm.call({
			method: "get_items",
			doc: me.frm.doc,
			freeze: true,
			callback: function(r) {
				if(!r.exc) {
					me.refresh_qty_warning_color();
					me.frm.save();
				}
			}
		});
	},

	ppk: function (doc, cdt, cdn) {
		var row = frappe.get_doc(cdt, cdn);
		this.log_local_changes('ppk', row.ppk, row);
	},

	physical_stock: function (doc, cdt, cdn) {
		var row = frappe.get_doc(cdt, cdn);
		this.log_local_changes('physical_stock', row.physical_stock, row);
	},

	calculate_totals: function () {
		var me = this;

		this.frm.doc.total_actual_qty = 0;
		this.frm.doc.total_po_qty = 0;
		this.frm.doc.total_available_qty = 0;
		this.frm.doc.total_so_qty = 0;
		this.frm.doc.total_short_excess = 0;
		this.frm.doc.total_physical_stock = 0;
		this.frm.doc.total_ppk = 0;
		this.frm.doc.total_net_short_excess = 0;

		$.each(this.frm.doc.items || [], function (i, d) {
			d.net_short_excess = flt(d.physical_stock) + flt(d.total_selected_po_qty) - flt(d.total_selected_so_qty) - flt(d.ppk);

			me.frm.doc.total_actual_qty += flt(d.actual_qty);
			me.frm.doc.total_po_qty += flt(d.total_selected_po_qty);
			me.frm.doc.total_available_qty += flt(d.total_available_qty);
			me.frm.doc.total_so_qty += flt(d.total_selected_so_qty);
			me.frm.doc.total_short_excess += flt(d.short_excess);
			me.frm.doc.total_physical_stock += flt(d.physical_stock);
			me.frm.doc.total_ppk += flt(d.ppk);
			me.frm.doc.total_net_short_excess += flt(d.net_short_excess);

			me.set_qty_warning_color(d);
		});

		this.frm.refresh_fields();
	},

	refresh_qty_warning_color: function () {
		var me = this;
		$.each(this.frm.doc.items || [], function (i, d) {
			me.set_qty_warning_color(d);
		});
	},

	set_qty_warning_color: function(item) {
		var color;
		if (flt(item.net_short_excess) < 0) {
			color = 'red';
		} else if (flt(item.net_short_excess) > 0) {
			color = 'green';
		} else {
			color = 'inherit';
		}

		var grid_row = this.frm.get_field("items").grid.get_grid_row(item.name);
		if (grid_row) {
			$("[data-fieldname='net_short_excess']", grid_row.wrapper)
				.css("color", color);
		}
	},

	log_local_changes: function (fieldname, value, row) {
		if (this.frm.is_new() || this.frm.doc.docstatus !== 0) {
			this.calculate_totals();
		} else {
			frappe.call({
				method: "erpnext.selling.doctype.qty_adjust_stock_count.qty_adjust_stock_count.handle_change",
				args: {
					name: this.frm.doc.name,
					fieldname: fieldname,
					value: value,
					item_code: row ? row.item_code : null
				}
			});
		}
	},

	doc_update: function () {
		if(!this.frm.doc.__islocal) {
			frappe.model.remove_from_locals(this.frm.doctype, this.frm.docname);
			return frappe.model.with_doc(this.frm.doctype, this.frm.docname, () => {
				this.frm.refresh();
			});
		}
	},

	setup_realtime: function () {
		var me = this;
		frappe.realtime.on('qty_adjust_stock_count_updated', function (data) {
			if (!frappe.get_doc(data.doctype, data.name)) {
				return;
			}

			if(frappe.get_route()[0] === "Form" && cur_frm.doc.doctype === data.doctype && cur_frm.doc.name === data.name) {
				if(!frappe.ui.form.is_saving) {
					frappe.model.sync(data);
					me.calculate_totals();
				}
			} else {
				frappe.model.remove_from_locals(data.doctype, data.name);
			}
		});
	},
});

$.extend(cur_frm.cscript, new erpnext.selling.QtyAdjustStockCountController({frm: cur_frm}));
