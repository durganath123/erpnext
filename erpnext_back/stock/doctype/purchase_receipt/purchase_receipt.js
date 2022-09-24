// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

{% include 'erpnext/public/js/controllers/buying.js' %};

frappe.provide("erpnext.stock");

frappe.ui.form.on("Purchase Receipt", {
	setup: (frm) => {
		frm.custom_make_buttons = {
			'Stock Entry': 'Return',
			'Purchase Invoice': 'Purchase Invoice',
			'Landed Cost Voucher': 'Landed Cost Voucher'
		};

		frm.set_query("expense_account", "items", function() {
			return {
				query: "erpnext.controllers.queries.get_expense_account",
				filters: {'company': frm.doc.company }
			}
		});
		
	},
	onload: function(frm) {
		erpnext.queries.setup_queries(frm, "Warehouse", function() {
			return erpnext.queries.warehouse(frm.doc);
		});
	},

	refresh: function(frm) {
		if(frm.doc.company) {
			frm.trigger("toggle_display_account_head");
		}

		if (frm.doc.docstatus === 1 && frm.doc.is_return === 1 && frm.doc.per_billed !== 100) {
			frm.add_custom_button(__('Debit Note'), function() {
				frappe.model.open_mapped_doc({
					method: "erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_invoice",
					frm: cur_frm,
				})
			}, __('Create'));
			frm.page.set_inner_btn_group_as_primary(__('Create'));
		}
	},

	company: function(frm) {
		frm.trigger("toggle_display_account_head");
	},

	toggle_display_account_head: function(frm) {
		var enabled = erpnext.is_perpetual_inventory_enabled(frm.doc.company)
		frm.fields_dict["items"].grid.set_column_disp(["cost_center"], enabled);
	},

	validate: function(frm) {
		for (var i = frm.fields_dict['items'].grid.grid_rows.length - 1; i >= 0; --i) {
			var grid_row = frm.fields_dict['items'].grid.grid_rows[i];
			if (!grid_row.doc.qty) {
				grid_row.remove();
			}
		}

		frm.cscript.set_naming_series();
	}
});

erpnext.stock.PurchaseReceiptController = erpnext.buying.BuyingController.extend({
	setup: function(doc) {
		this.setup_posting_date_time_check();
		this._super(doc);
	},

	refresh: function() {
		var me = this;
		this._super();

		if (this.frm.doc.docstatus < 2 && !this.frm.doc.__islocal && !this.frm.doc.is_return) {
			this.frm.add_custom_button(__('Print Box Labels'), () => this.show_print_item_labels_dialog("box"));
			this.frm.add_custom_button(__('Print Pallet Labels'), () => this.show_print_item_labels_dialog("pallet"));
		}

		if(this.frm.doc.docstatus===1) {
			this.show_stock_ledger();
			//removed for temporary
			this.show_general_ledger();

			this.frm.add_custom_button(__('Asset'), function() {
				frappe.route_options = {
					purchase_receipt: me.frm.doc.name,
				};
				frappe.set_route("List", "Asset");
			}, __("View"));

			this.frm.add_custom_button(__('Asset Movement'), function() {
				frappe.route_options = {
					reference_name: me.frm.doc.name,
				};
				frappe.set_route("List", "Asset Movement");
			}, __("View"));
		}

		if(!this.frm.doc.is_return && this.frm.doc.status!="Closed") {
			if (this.frm.doc.docstatus == 0) {
				this.frm.add_custom_button(__('Purchase Order'),
					function () {
						erpnext.utils.map_current_doc({
							method: "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_receipt",
							source_doctype: "Purchase Order",
							target: me.frm,
							setters: {
								supplier: me.frm.doc.supplier || undefined,
							},
							get_query_filters: {
								docstatus: 1,
								status: ["not in", ["Closed", "On Hold"]],
								per_received: ["<", 99.99],
								company: me.frm.doc.company
							}
						})
					}, __("Get items from"));
			}

			if(this.frm.doc.docstatus == 1 && this.frm.doc.status!="Closed") {
				if (this.frm.has_perm("submit")) {
					cur_frm.add_custom_button(__("Close"), this.close_purchase_receipt, __("Status"))
				}

				cur_frm.add_custom_button(__('Purchase Return'), this.make_purchase_return, __('Create'));

				if(flt(this.frm.doc.per_completed) < 100) {
					cur_frm.add_custom_button(__('Purchase Invoice'), this.make_purchase_invoice, __("Create"));
				}
				cur_frm.add_custom_button(__('Retention Stock Entry'), this.make_retention_stock_entry, __('Create'));

				if(!this.frm.doc.auto_repeat) {
					cur_frm.add_custom_button(__('Subscription'), function() {
						erpnext.utils.make_subscription(me.frm.doc.doctype, me.frm.doc.name)
					}, __('Create'))
				}

				cur_frm.add_custom_button(__('Landed Cost Voucher'), this.make_landed_cost_voucher, __("Create"));

				cur_frm.page.set_inner_btn_group_as_primary(__("Create"));
			}
		}


		if(this.frm.doc.docstatus==1 && this.frm.doc.status === "Closed" && this.frm.has_perm("submit")) {
			cur_frm.add_custom_button(__('Reopen'), this.reopen_purchase_receipt, __("Status"))
		}

		this.frm.toggle_reqd("supplier_warehouse", this.frm.doc.is_subcontracted==="Yes");

		this.set_naming_series();
	},

	show_print_item_labels_dialog: function(medium) {
		const me = this;
		this.build_print_item_labels_dialog(function () {
			let out = [];
			$.each(me.frm.doc.items || [], function (i, d) {
				if (d.item_code) {
					out.push({
						'name': d.name,
						'item_code': d.item_code,
						'item_name': d.item_name,
						'batch_no': d.batch_no,
						'print_qty': medium == "pallet" ? Math.ceil(d.pallets) : Math.ceil(d.qty),
						'alt_uom': d.alt_uom,
						'alt_uom_size': d.alt_uom_size_std,
						'supplier_name': me.frm.doc.supplier_name || me.frm.doc.supplier,
						'received_date': me.frm.doc.posting_date
					});
				}
			});
			return out;
		}, {
			fields: [{
				fieldtype: 'Link',
				fieldname: "batch_no",
				options: "Batch",
				read_only: 1,
				in_list_view: 1,
				label: __('Batch')
			}, {
				fieldtype: 'Link',
				fieldname: "item_code",
				options: "Item",
				read_only: 1,
				label: __('Item Code')
			}, {
				fieldtype: 'Data',
				fieldname: "item_name",
				read_only: 1,
				in_list_view: 1,
				label: __('Item Name')
			}, {
				fieldtype: 'Float',
				fieldname: "alt_uom_size",
				read_only: 1,
				label: __('Per Unit')
			}, {
				fieldtype: 'Link',
				fieldname: "alt_uom",
				read_only: 1,
				options: "UOM",
				label: __('Contents UOM')
			}, {
				fieldtype: 'Int',
				fieldname: "print_qty",
				in_list_view: 1,
				label: __('Print Qty')
			}, {
				fieldtype: 'Data',
				fieldname: "supplier_name",
				read_only: 1,
				label: __('Supplier Name')
			}, {
				fieldtype: 'Date',
				fieldname: "received_date",
				read_only: 1,
				label: __('Received Date')
			}]
		}, d => d.name.toLowerCase().includes(medium));
	},

	set_naming_series: function() {
		if (this.frm.doc.docstatus === 0) {
			if (this.frm.doc.is_return) {
				this.frm.set_value('naming_series', 'PREC-RET-');
			} else {
				this.frm.set_value('naming_series', 'PREC-');
			}
		}
	},

	make_purchase_invoice: function() {
		frappe.model.open_mapped_doc({
			method: "erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_invoice",
			frm: cur_frm
		})
	},

	make_purchase_return: function() {
		frappe.model.open_mapped_doc({
			method: "erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_return",
			frm: cur_frm
		})
	},

	close_purchase_receipt: function() {
		cur_frm.cscript.update_status("Closed");
	},

	reopen_purchase_receipt: function() {
		cur_frm.cscript.update_status("Submitted");
	},

	make_retention_stock_entry: function() {
		frappe.call({
			method: "erpnext.stock.doctype.stock_entry.stock_entry.move_sample_to_retention_warehouse",
			args:{
				"company": cur_frm.doc.company,
				"items": cur_frm.doc.items
			},
			callback: function (r) {
				if (r.message) {
					var doc = frappe.model.sync(r.message)[0];
					frappe.set_route("Form", doc.doctype, doc.name);
				}
				else {
					frappe.msgprint(__("Purchase Receipt doesn't have any Item for which Retain Sample is enabled."));
				}
			}
		});
	},

});

// for backward compatibility: combine new and previous states
$.extend(cur_frm.cscript, new erpnext.stock.PurchaseReceiptController({frm: cur_frm}));

cur_frm.cscript.update_status = function(status) {
	frappe.ui.form.is_saving = true;
	frappe.call({
		method:"erpnext.stock.doctype.purchase_receipt.purchase_receipt.update_purchase_receipt_status",
		args: {docname: cur_frm.doc.name, status: status},
		callback: function(r){
			if(!r.exc)
				cur_frm.reload_doc();
		},
		always: function(){
			frappe.ui.form.is_saving = false;
		}
	})
}

cur_frm.fields_dict['items'].grid.get_field('project').get_query = function(doc, cdt, cdn) {
	return {
		filters: [
			['Project', 'status', 'not in', 'Completed, Cancelled']
		]
	}
}

cur_frm.cscript.select_print_heading = function(doc, cdt, cdn) {
	if(doc.select_print_heading)
		cur_frm.pformat.print_heading = doc.select_print_heading;
	else
		cur_frm.pformat.print_heading = "Purchase Receipt";
}

cur_frm.fields_dict['select_print_heading'].get_query = function(doc, cdt, cdn) {
	return {
		filters: [
			['Print Heading', 'docstatus', '!=', '2']
		]
	}
}

cur_frm.fields_dict['items'].grid.get_field('bom').get_query = function(doc, cdt, cdn) {
	var d = locals[cdt][cdn]
	return {
		filters: [
			['BOM', 'item', '=', d.item_code],
			['BOM', 'is_active', '=', '1'],
			['BOM', 'docstatus', '=', '1']
		]
	}
}

frappe.provide("erpnext.buying");

frappe.ui.form.on("Purchase Receipt", "is_subcontracted", function(frm) {
	if (frm.doc.is_subcontracted === "Yes") {
		erpnext.buying.get_default_bom(frm);
	}
	frm.toggle_reqd("supplier_warehouse", frm.doc.is_subcontracted==="Yes");
});

frappe.ui.form.on('Purchase Receipt Item', {
	item_code: function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		frappe.db.get_value('Item', {name: d.item_code}, 'sample_quantity', (r) => {
			frappe.model.set_value(cdt, cdn, "sample_quantity", r.sample_quantity);
			validate_sample_quantity(frm, cdt, cdn);
		});
	},
	qty: function(frm, cdt, cdn) {
		validate_sample_quantity(frm, cdt, cdn);
	},
	sample_quantity: function(frm, cdt, cdn) {
		validate_sample_quantity(frm, cdt, cdn);
	},
	batch_no: function(frm, cdt, cdn) {
		validate_sample_quantity(frm, cdt, cdn);
	},
});

cur_frm.cscript['Make Stock Entry'] = function() {
	frappe.model.open_mapped_doc({
		method: "erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_stock_entry",
		frm: cur_frm,
	})
}

var validate_sample_quantity = function(frm, cdt, cdn) {
	var d = locals[cdt][cdn];
	if (d.sample_quantity && d.qty) {
		frappe.call({
			method: 'erpnext.stock.doctype.stock_entry.stock_entry.validate_sample_quantity',
			args: {
				batch_no: d.batch_no,
				item_code: d.item_code,
				sample_quantity: d.sample_quantity,
				qty: d.qty
			},
			callback: (r) => {
				frappe.model.set_value(cdt, cdn, "sample_quantity", r.message);
			}
		});
	}
};
