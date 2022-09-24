// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

erpnext.taxes_and_totals = erpnext.payments.extend({
	setup: function() {},
	apply_pricing_rule_on_item: function(item){
		let effective_item_rate = item.price_list_rate;
		if (item.parenttype === "Sales Order" && item.blanket_order_rate) {
			effective_item_rate = item.blanket_order_rate;
		}
		if(item.margin_type == "Percentage"){
			item.rate_with_margin = flt(effective_item_rate)
				+ flt(effective_item_rate) * ( flt(item.margin_rate_or_amount) / 100);
		} else {
			item.rate_with_margin = flt(effective_item_rate) + flt(item.margin_rate_or_amount);
		}
		item.base_rate_with_margin = flt(item.rate_with_margin) * flt(this.frm.doc.conversion_rate);

		item.rate = flt(item.rate_with_margin , precision("rate", item));

		if(item.discount_percentage) {
			item.discount_amount = flt(item.rate_with_margin) * flt(item.discount_percentage) / 100;
		}

		if (item.discount_amount) {
			item.rate = flt((item.rate_with_margin) - (item.discount_amount), precision('rate', item));
		} else {
			item.discount_amount = 0;
		}
	},

	calculate_taxes_and_totals: function(update_paid_amount) {
		this.discount_amount_applied = false;
		this._calculate_taxes_and_totals();
		this.calculate_discount_amount();

		// Advance calculation applicable to Sales /Purchase Invoice
		if(in_list(["Sales Invoice", "Purchase Invoice"], this.frm.doc.doctype)
			&& this.frm.doc.docstatus < 2 && !this.frm.doc.is_return) {
			this.calculate_total_advance(update_paid_amount);
		}

		// Sales person's commission
		if(in_list(["Quotation", "Sales Order", "Delivery Note", "Sales Invoice"], this.frm.doc.doctype)) {
			this.calculate_commission();
			this.calculate_contribution();
		}

		// Update paid amount on return/debit note creation
		if(this.frm.doc.doctype === "Purchase Invoice" && this.frm.doc.is_return
			&& (this.frm.doc.grand_total > this.frm.doc.paid_amount)) {
			this.frm.doc.paid_amount = flt(this.frm.doc.grand_total, precision("grand_total"));
		}

		this.frm.refresh_fields();
	},

	calculate_discount_amount: function(){
		if (frappe.meta.get_docfield(this.frm.doc.doctype, "discount_amount")) {
			this.set_discount_amount();
			this.apply_discount_amount();
		}
	},

	_calculate_taxes_and_totals: function() {
		this.validate_conversion_rate();
		this.calculate_item_values();
		this.initialize_taxes();
		this.determine_exclusive_rate();
		this.calculate_net_total();
		this.calculate_landed_rate();
		this.calculate_taxes();
		this.manipulate_grand_total_for_inclusive_tax();
		this.calculate_totals();
		this.calculate_delivery_charges();
		this.calculate_gross_profit();
		this._cleanup();
	},

	validate_conversion_rate: function() {
		this.frm.doc.conversion_rate = flt(this.frm.doc.conversion_rate, (cur_frm) ? precision("conversion_rate") : 9);
		var conversion_rate_label = frappe.meta.get_label(this.frm.doc.doctype, "conversion_rate",
			this.frm.doc.name);
		var company_currency = this.get_company_currency();

		if(!this.frm.doc.conversion_rate) {
			if(this.frm.doc.currency == company_currency) {
				this.frm.set_value("conversion_rate", 1);
			} else {
				const err_message = __('{0} is mandatory. Maybe Currency Exchange record is not created for {1} to {2}', [
					conversion_rate_label,
					this.frm.doc.currency,
					company_currency
				]);
				frappe.throw(err_message);
			}
		}
	},

	calculate_item_values: function() {
		var me = this;

		if (!this.discount_amount_applied) {
			$.each(this.frm.doc["items"] || [], function(i, item) {
				frappe.model.round_floats_in(item);

				item.alt_uom_size_std = item.alt_uom ? item.stock_alt_uom_size_std * item.conversion_factor : 1.0;
				item.alt_uom_size_std = item.alt_uom_size_std || 1.0;

				item.alt_uom_size = item.alt_uom ? item.stock_alt_uom_size * item.conversion_factor : 1.0;
				item.alt_uom_qty = item.alt_uom ? flt(item.qty * item.alt_uom_size, precision('alt_uom_qty', item))
					: item.qty;

				var has_margin_field = frappe.meta.has_field(item.doctype, 'margin_type');
				if(has_margin_field && flt(item.rate_with_margin) > 0) {
					item.amount_before_discount = flt((item.rate_with_margin / item.alt_uom_size_std) * item.alt_uom_qty, precision("amount_before_discount", item));
				} else if(flt(item.price_list_rate) > 0) {
					item.amount_before_discount = flt((item.price_list_rate / item.alt_uom_size_std) * item.alt_uom_qty, precision("amount_before_discount", item));
				} else {
					item.amount_before_discount = flt((item.rate / item.alt_uom_size_std) * item.alt_uom_qty, precision("amount_before_discount", item));
				}

				item.alt_uom_rate = flt(item.rate / (item.alt_uom_size_std || 1));
				item.amount = flt(item.alt_uom_rate * item.alt_uom_qty,	precision("amount", item));

				item.net_rate = item.rate;
				item.net_amount = item.amount;
				item.total_discount = flt(item.amount_before_discount - item.amount, precision("total_discount", item));

				item.tax_exclusive_price_list_rate = item.price_list_rate;
				item.tax_exclusive_rate = item.rate;
				item.tax_exclusive_amount = item.amount;
				item.tax_exclusive_discount_amount = item.discount_amount;
				item.tax_exclusive_amount_before_discount = item.amount_before_discount;
				item.tax_exclusive_total_discount = item.total_discount;
				if(has_margin_field) {
					item.tax_exclusive_rate_with_margin = item.rate_with_margin;
					item.base_tax_exclusive_rate_with_margin = item.base_rate_with_margin;
				}

				item.item_tax_amount = 0.0;
				item.total_weight = flt(item.weight_per_unit * item.stock_qty);
				item.total_weight_kg = flt(item.total_weight * 0.45359237);
				item.volume_cuft = flt(item.volume_per_unit_cuft * item.stock_qty);

				me.set_in_company_currency(item, ["price_list_rate", "rate", "alt_uom_rate", "amount", "net_rate", "net_amount",
					"tax_exclusive_price_list_rate", "tax_exclusive_rate", "tax_exclusive_amount",
					"amount_before_discount", "total_discount", "tax_exclusive_amount_before_discount", "tax_exclusive_total_discount"]);
			});
		}
	},

	set_in_company_currency: function(doc, fields, do_not_round_before_conversion) {
		var me = this;
		$.each(fields, function(i, f) {
			var v = do_not_round_before_conversion ? flt(doc[f]) : flt(doc[f], precision(f, doc));
			doc["base_"+f] = flt(v * me.frm.doc.conversion_rate, precision("base_" + f, doc));
		});
	},

	should_round_transaction_currency: function() {
		return !cint(this.frm.doc.calculate_tax_on_company_currency)
			|| !this.frm.doc.currency || this.frm.doc.currency == this.get_company_currency();
	},

	initialize_taxes: function() {
		var me = this;

		$.each(this.frm.doc["taxes"] || [], function(i, tax) {
			tax.item_wise_tax_detail = {};
			var tax_fields = ["total", "tax_amount_after_discount_amount",
				"tax_amount_for_current_item", "grand_total_for_current_item",
				"tax_fraction_for_current_item", "grand_total_fraction_for_current_item"];

			if (cstr(tax.charge_type) != "Actual" && cstr(tax.charge_type) != "Weighted Distribution" &&
				!(me.discount_amount_applied && me.frm.doc.apply_discount_on=="Grand Total")) {
				tax_fields.push("tax_amount");
			}

			$.each(tax_fields, function(i, fieldname) { tax[fieldname] = 0.0; });

			if (!this.discount_amount_applied && cur_frm) {
				cur_frm.cscript.validate_taxes_and_charges(tax.doctype, tax.name);
				me.validate_inclusive_tax(tax);
			}

			if (me.should_round_transaction_currency()) {
				frappe.model.round_floats_in(tax);
			} else {
				frappe.model.round_floats_in(tax, ["rate"]);
			}
		});
	},

	determine_exclusive_rate: function() {
		var me = this;

		var has_inclusive_tax = false;
		$.each(me.frm.doc["taxes"] || [], function(i, row) {
			if(cint(row.included_in_print_rate)) has_inclusive_tax = true;
		});

		$.each(me.frm.doc["items"] || [], function(i, item) {
			item.cumulated_tax_fraction = 0.0;
		});

		if(!has_inclusive_tax) return;

		$.each(me.frm.doc["items"] || [], function(n, item) {
			var item_tax_map = me._load_item_tax_rate(item.item_tax_rate);

			$.each(me.frm.doc["taxes"] || [], function(i, tax) {
				tax.tax_fraction_for_current_item = me.get_current_tax_fraction(tax, item_tax_map);

				if(i==0) {
					tax.grand_total_fraction_for_current_item = 1 + tax.tax_fraction_for_current_item;
				} else {
					tax.grand_total_fraction_for_current_item =
						me.frm.doc["taxes"][i-1].grand_total_fraction_for_current_item +
						tax.tax_fraction_for_current_item;
				}

				item.cumulated_tax_fraction += tax.tax_fraction_for_current_item;
			});

			if(item.cumulated_tax_fraction && !me.discount_amount_applied) {
				var rate_before_discount = flt(item.tax_exclusive_price_list_rate / (1 + item.cumulated_tax_fraction));
				item.tax_exclusive_price_list_rate = flt(rate_before_discount);

				item.tax_exclusive_amount = flt(item.amount / (1 + item.cumulated_tax_fraction));
				item.tax_exclusive_rate = item.qty ? (item.tax_exclusive_amount / item.qty)
					: (item.rate / (1 + item.cumulated_tax_fraction));

				var has_margin_field = frappe.meta.has_field(item.doctype, 'margin_type');
				if(has_margin_field && flt(item.tax_exclusive_rate_with_margin) > 0) {
					rate_before_discount = item.tax_exclusive_rate_with_margin / (1 + item.cumulated_tax_fraction);
					item.tax_exclusive_rate_with_margin = flt(rate_before_discount);
					item.base_tax_exclusive_rate_with_margin = flt(item.tax_exclusive_rate_with_margin * me.frm.doc.conversion_rate);
					item.tax_exclusive_discount_amount = flt(item.tax_exclusive_rate_with_margin - item.tax_exclusive_rate);
				} else if(flt(item.tax_exclusive_price_list_rate) > 0) {
					item.tax_exclusive_discount_amount = flt(item.tax_exclusive_price_list_rate - item.tax_exclusive_rate);
				}

				item.tax_exclusive_amount_before_discount = flt(rate_before_discount * item.qty,
					precision("tax_exclusive_amount_before_discount", item));
				item.tax_exclusive_total_discount = flt(item.tax_exclusive_amount_before_discount - item.tax_exclusive_amount,
					precision("tax_exclusive_total_discount", item));

				item.net_amount = flt(item.amount / (1 + item.cumulated_tax_fraction));
				item.net_rate = item.qty ? flt(item.net_amount / item.qty, precision("net_rate", item)) : 0;

				me.set_in_company_currency(item, ["net_rate", "net_amount",
					"tax_exclusive_price_list_rate", "tax_exclusive_rate", "tax_exclusive_amount",
					"tax_exclusive_amount_before_discount", "tax_exclusive_total_discount"]);
			}
		});
	},

	get_current_tax_fraction: function(tax, item_tax_map) {
		// Get tax fraction for calculating tax exclusive amount
		// from tax inclusive amount
		var current_tax_fraction = 0.0;

		if(cint(tax.included_in_print_rate)) {
			var tax_rate = this._get_tax_rate(tax, item_tax_map);

			if(tax.charge_type == "On Net Total") {
				current_tax_fraction = (tax_rate / 100.0);

			} else if(tax.charge_type == "On Previous Row Amount") {
				current_tax_fraction = (tax_rate / 100.0) *
					this.frm.doc["taxes"][cint(tax.row_id) - 1].tax_fraction_for_current_item;

			} else if(tax.charge_type == "On Previous Row Total") {
				current_tax_fraction = (tax_rate / 100.0) *
					this.frm.doc["taxes"][cint(tax.row_id) - 1].grand_total_fraction_for_current_item;
			}
		}

		if(tax.add_deduct_tax) {
			current_tax_fraction *= (tax.add_deduct_tax == "Deduct") ? -1.0 : 1.0;
		}
		return current_tax_fraction;
	},

	_get_tax_rate: function(tax, item_tax_map) {
		return (Object.keys(item_tax_map).indexOf(tax.account_head) != -1) ?
			flt(item_tax_map[tax.account_head], precision("rate", tax)) : tax.rate;
	},

	calculate_net_total: function() {
		var me = this;
		this.frm.doc.total_qty = this.frm.doc.total = this.frm.doc.base_total = this.frm.doc.net_total = this.frm.doc.base_net_total = 0.0;
		this.frm.doc.total_alt_uom_qty = 0;
		this.frm.doc.base_tax_exclusive_total = this.frm.doc.tax_exclusive_total = 0.0;
		this.frm.doc.base_total_discount = this.frm.doc.total_discount = 0.0;
		this.frm.doc.base_total_before_discount = this.frm.doc.total_before_discount = 0.0;
		this.frm.doc.base_tax_exclusive_total_before_discount = this.frm.doc.tax_exclusive_total_before_discount = 0.0;
		this.frm.doc.base_tax_exclusive_total_discount = this.frm.doc.tax_exclusive_total_discount = 0.0;

		$.each(this.frm.doc["items"] || [], function(i, item) {
			me.frm.doc.total_qty += item.qty;
			me.frm.doc.total_alt_uom_qty += item.alt_uom_qty;

			me.frm.doc.total += item.amount;
			me.frm.doc.base_total += item.base_amount;

			me.frm.doc.tax_exclusive_total += item.tax_exclusive_amount;
			me.frm.doc.base_tax_exclusive_total += item.base_tax_exclusive_amount;

			me.frm.doc.total_before_discount += item.amount_before_discount;
			me.frm.doc.base_total_before_discount += item.base_amount_before_discount;
			me.frm.doc.tax_exclusive_total_before_discount += item.tax_exclusive_amount_before_discount;
			me.frm.doc.base_tax_exclusive_total_before_discount += item.base_tax_exclusive_amount_before_discount;

			me.frm.doc.total_discount += item.total_discount;
			me.frm.doc.base_total_discount += item.base_total_discount;
			me.frm.doc.tax_exclusive_total_discount += item.tax_exclusive_total_discount;
			me.frm.doc.base_tax_exclusive_total_discount += item.base_tax_exclusive_total_discount;

			me.frm.doc.net_total += item.net_amount;
			me.frm.doc.base_net_total += item.base_net_amount;
		});

		me.frm.doc.actual_boxes = me.frm.doc.total_qty;

		frappe.model.round_floats_in(this.frm.doc, ["total", "base_total", "net_total", "base_net_total",
			"tax_exclusive_total", "base_tax_exclusive_total",
			"total_before_discount", "total_discount", "base_total_before_discount", "base_total_discount",
			"tax_exclusive_total_before_discount", "tax_exclusive_total_discount",
			"base_tax_exclusive_total_before_discount", "base_tax_exclusive_total_discount"]);
	},

	calculate_landed_rate: function() {
		if (this.frm.doc.doctype === 'Purchase Order') {
			$.each(this.frm.doc["items"] || [], function (i, item) {
				item.landed_rate = item.qty ? (flt(item.base_net_amount) + flt(item.landed_cost_voucher_amount)) / flt(item.qty) : 0
			});
		}
	},

	calculate_taxes: function() {
		var me = this;
		this.frm.doc.rounding_adjustment = 0;
		var actual_tax_dict = {};
		var weighted_distrubution_tax_on_net_total = {};

		// maintain actual tax rate based on idx
		$.each(this.frm.doc["taxes"] || [], function(i, tax) {
			if (tax.charge_type == "Actual" || tax.charge_type == "Weighted Distribution") {
				if (me.should_round_transaction_currency()) {
					actual_tax_dict[tax.idx] = flt(tax.tax_amount, precision("tax_amount", tax));
				} else {
					actual_tax_dict[tax.idx] = tax.tax_amount;
				}
			}
		});

		// Tax on Net Total for Weighted Distribution
		$.each(this.frm.doc["items"] || [], function(n, item) {
			var item_tax_map = me._load_item_tax_rate(item.item_tax_rate);

			$.each(me.frm.doc["taxes"] || [], function (i, tax) {
				if (tax.charge_type == "Weighted Distribution") {
					if (!weighted_distrubution_tax_on_net_total[tax.idx]) {
						weighted_distrubution_tax_on_net_total[tax.idx] = 0.0;
					}
					var tax_rate = me._get_tax_rate(tax, item_tax_map);
					weighted_distrubution_tax_on_net_total[tax.idx] += (tax_rate / 100) * item.net_amount;
				}
			});
		});

		$.each(this.frm.doc["items"] || [], function(n, item) {
			var item_tax_map = me._load_item_tax_rate(item.item_tax_rate);
			$.each(me.frm.doc["taxes"] || [], function(i, tax) {
				// tax_amount represents the amount of tax for the current step
				var current_tax_amount = me.get_current_tax_amount(item, tax, item_tax_map, weighted_distrubution_tax_on_net_total);

				// Adjust divisional loss to the last item
				if (tax.charge_type == "Actual" || tax.charge_type == "Weighted Distribution") {
					actual_tax_dict[tax.idx] -= current_tax_amount;
					if (n == me.frm.doc["items"].length - 1) {
						current_tax_amount += actual_tax_dict[tax.idx];
					}
				}

				// accumulate tax amount into tax.tax_amount
				if (tax.charge_type != "Actual" && tax.charge_type != "Weighted Distribution" &&
					!(me.discount_amount_applied && me.frm.doc.apply_discount_on=="Grand Total")) {
					tax.tax_amount += current_tax_amount;
				}

				// store tax_amount for current item as it will be used for
				// charge type = 'On Previous Row Amount'
				tax.tax_amount_for_current_item = current_tax_amount;

				// tax amount after discount amount
				tax.tax_amount_after_discount_amount += current_tax_amount;

				// for buying
				if(tax.category) {
					// if just for valuation, do not add the tax amount in total
					// hence, setting it as 0 for further steps
					current_tax_amount = (tax.category == "Valuation") ? 0.0 : current_tax_amount;

					current_tax_amount *= (tax.add_deduct_tax == "Deduct") ? -1.0 : 1.0;
				}

				// note: grand_total_for_current_item contains the contribution of
				// item's amount, previously applied tax and the current tax on that item
				if(i==0) {
					tax.grand_total_for_current_item = flt(item.net_amount + current_tax_amount);
				} else {
					tax.grand_total_for_current_item =
						flt(me.frm.doc["taxes"][i-1].grand_total_for_current_item + current_tax_amount);
				}

				// set precision in the last item iteration
				if (n == me.frm.doc["items"].length - 1) {
					me.round_off_totals(tax);

					// in tax.total, accumulate grand total for each item
					me.set_cumulative_total(i, tax);

					me.set_in_company_currency(tax,
						["total", "displayed_total", "tax_amount", "tax_amount_after_discount_amount"],
						!me.should_round_transaction_currency());

					// adjust Discount Amount loss in last tax iteration
					if ((i == me.frm.doc["taxes"].length - 1) && me.discount_amount_applied
						&& me.frm.doc.apply_discount_on == "Grand Total" && me.frm.doc.discount_amount) {
						me.frm.doc.rounding_adjustment = flt(me.frm.doc.grand_total -
							flt(me.frm.doc.discount_amount) - tax.total, precision("rounding_adjustment"));
					}
				}
			});
		});
	},

	set_cumulative_total: function(row_idx, tax) {
		var tax_amount = tax.tax_amount_after_discount_amount;
		var tax_amount_before_discount = tax.tax_amount;
		if (tax.category == 'Valuation') {
			tax_amount = 0;
			tax_amount_before_discount = 0;
		}
		if (tax.add_deduct_tax == "Deduct")
		{
			tax_amount = -1*tax_amount;
			tax_amount_before_discount = -1*tax_amount_before_discount;
		}

		if(row_idx==0) {
			tax.total = this.frm.doc.net_total + tax_amount;

			if (this.frm.doc.apply_discount_on == "Grand Total") {
				tax.displayed_total = this.frm.doc.tax_exclusive_total + tax_amount_before_discount;
			} else {
				tax.displayed_total = tax.total;
			}
		} else {
			tax.total = this.frm.doc["taxes"][row_idx-1].total + tax_amount;

			if (this.frm.doc.apply_discount_on == "Grand Total") {
				tax.displayed_total = this.frm.doc["taxes"][row_idx - 1].displayed_total + tax_amount_before_discount;
			} else {
				tax.displayed_total = tax.total;
			}
		}

		if (this.should_round_transaction_currency()) {
			tax.total = flt(tax.total, precision("total", tax));
			tax.displayed_total = flt(tax.displayed_total, precision("displayed_total", tax));
		}
	},

	_load_item_tax_rate: function(item_tax_rate) {
		return item_tax_rate ? JSON.parse(item_tax_rate) : {};
	},

	get_current_tax_amount: function(item, tax, item_tax_map, weighted_distrubution_tax_on_net_total) {
		var tax_rate = this._get_tax_rate(tax, item_tax_map);
		var current_tax_amount = 0.0;

		if(tax.charge_type == "Actual" || tax.charge_type == "Weighted Distribution") {
			// distribute the tax amount proportionally to each item row
			var actual = this.should_round_transaction_currency() ?
				flt(tax.tax_amount, precision("tax_amount", tax)) : flt(tax.tax_amount);

			if (tax.charge_type == "Actual" || !weighted_distrubution_tax_on_net_total[tax.idx]) {
				current_tax_amount = this.frm.doc.net_total ?
					((item.net_amount / this.frm.doc.net_total) * actual) : 0.0;
			} else {
				var tax_on_net_amount = (tax_rate / 100.0) * item.net_amount;
				var tax_on_net_total = weighted_distrubution_tax_on_net_total[tax.idx];
				current_tax_amount = actual * (tax_on_net_amount / tax_on_net_total);
			}

		} else if(tax.charge_type == "On Net Total") {
			current_tax_amount = (tax_rate / 100.0) * item.net_amount;
		} else if(tax.charge_type == "On Previous Row Amount") {
			current_tax_amount = (tax_rate / 100.0) *
				this.frm.doc["taxes"][cint(tax.row_id) - 1].tax_amount_for_current_item;

		} else if(tax.charge_type == "On Previous Row Total") {
			current_tax_amount = (tax_rate / 100.0) *
				this.frm.doc["taxes"][cint(tax.row_id) - 1].grand_total_for_current_item;
		}

		this.set_item_wise_tax(item, tax, tax_rate, current_tax_amount);

		return current_tax_amount;
	},

	set_item_wise_tax: function(item, tax, tax_rate, current_tax_amount) {
		// store tax breakup for each item
		let tax_detail = tax.item_wise_tax_detail;
		let key = item.item_code || item.item_name;

		let item_wise_tax_amount = current_tax_amount * this.frm.doc.conversion_rate;
		if (tax_detail && tax_detail[key])
			item_wise_tax_amount += tax_detail[key][1];

		tax_detail[key] = [tax_rate, flt(item_wise_tax_amount, precision("base_tax_amount", tax))];
	},

	round_off_totals: function(tax) {
		if (this.should_round_transaction_currency()) {
			tax.tax_amount = flt(tax.tax_amount, precision("tax_amount", tax));
			tax.tax_amount_after_discount_amount = flt(tax.tax_amount_after_discount_amount, precision("tax_amount", tax));
		}
	},

	manipulate_grand_total_for_inclusive_tax: function() {
		var me = this;
		// if fully inclusive taxes and diff
		if (this.frm.doc["taxes"] && this.frm.doc["taxes"].length) {
			var any_inclusive_tax = false;
			$.each(this.frm.doc.taxes || [], function(i, d) {
				if(cint(d.included_in_print_rate)) any_inclusive_tax = true;
			});
			if (any_inclusive_tax) {
				var last_tax = me.frm.doc["taxes"].slice(-1)[0];
				var non_inclusive_tax_amount = frappe.utils.sum($.map(this.frm.doc.taxes || [],
					function(d) {
						if(!d.included_in_print_rate) {
							return flt(d.tax_amount_after_discount_amount);
						}
					}
				));
				var diff = me.frm.doc.total + non_inclusive_tax_amount
					- flt(last_tax.total, precision("grand_total"));

				if(me.discount_amount_applied && me.frm.doc.discount_amount) {
					diff -= flt(me.frm.doc.discount_amount);
				}

				diff = flt(diff, precision("rounding_adjustment"));

				if ( diff && Math.abs(diff) <= (5.0 / Math.pow(10, precision("tax_amount", last_tax))) ) {
					me.frm.doc.rounding_adjustment = diff;
				}
			}
		}
	},

	calculate_totals: function() {
		// Changing sequence can cause rounding_adjustmentng issue and on-screen discrepency
		var me = this;
		var tax_count = this.frm.doc["taxes"] ? this.frm.doc["taxes"].length : 0;
		this.frm.doc.grand_total = flt(tax_count
			? this.frm.doc["taxes"][tax_count - 1].total + flt(this.frm.doc.rounding_adjustment)
			: this.frm.doc.net_total);

		if(in_list(["Quotation", "Sales Order", "Delivery Note", "Sales Invoice"], this.frm.doc.doctype)) {
			this.frm.doc.base_grand_total = (this.frm.doc.total_taxes_and_charges) ?
				flt(this.frm.doc.grand_total * this.frm.doc.conversion_rate) : this.frm.doc.base_net_total;
		} else {
			// other charges added/deducted
			this.frm.doc.taxes_and_charges_added = this.frm.doc.taxes_and_charges_deducted = 0.0;
			if(tax_count) {
				$.each(this.frm.doc["taxes"] || [], function(i, tax) {
					if (in_list(["Valuation and Total", "Total"], tax.category)) {
						if(tax.add_deduct_tax == "Add") {
							me.frm.doc.taxes_and_charges_added += flt(tax.tax_amount_after_discount_amount);
						} else {
							me.frm.doc.taxes_and_charges_deducted += flt(tax.tax_amount_after_discount_amount);
						}
					}
				});

				if (this.should_round_transaction_currency()) {
					frappe.model.round_floats_in(this.frm.doc,
						["taxes_and_charges_added", "taxes_and_charges_deducted"]);
				}
			}

			this.frm.doc.base_grand_total = flt((this.frm.doc.taxes_and_charges_added || this.frm.doc.taxes_and_charges_deducted) ?
				flt(this.frm.doc.grand_total * this.frm.doc.conversion_rate) : this.frm.doc.base_net_total);

			this.set_in_company_currency(this.frm.doc,
				["taxes_and_charges_added", "taxes_and_charges_deducted"],
				!this.should_round_transaction_currency());
		}

		this.frm.doc.total_taxes_and_charges = this.frm.doc.grand_total - this.frm.doc.net_total - flt(this.frm.doc.rounding_adjustment);
		if (this.should_round_transaction_currency()) {
			this.frm.doc.total_taxes_and_charges = flt(this.frm.doc.total_taxes_and_charges, precision("total_taxes_and_charges"));
		}

		this.set_in_company_currency(this.frm.doc, ["total_taxes_and_charges", "rounding_adjustment"],
			!this.should_round_transaction_currency());

		// Round grand total as per precision
		if (this.should_round_transaction_currency()) {
			frappe.model.round_floats_in(this.frm.doc, ["grand_total"]);
		}
		frappe.model.round_floats_in(this.frm.doc, ["base_grand_total"]);

		// rounded totals
		this.set_rounded_total();
	},

	calculate_delivery_charges: function() {
		if (frappe.meta.get_docfield(this.frm.doc.doctype, 'delivery_charges', this.frm.doc.name)) {
			this.frm.doc.delivery_charges = 0;

			var delivery_charges_account = frappe.get_doc(":Company", this.frm.doc.company).delivery_charges_account;
			if (delivery_charges_account) {
				this.frm.doc.delivery_charges = frappe.utils.sum((this.frm.doc.taxes || [])
					.filter(tax => tax.account_head == delivery_charges_account)
					.map(tax => flt(tax.tax_amount)));
			}

			this.frm.doc.delivery_charges = flt(this.frm.doc.delivery_charges, precision('delivery_charges'));
			this.frm.doc.total_taxes = this.frm.doc.total_taxes_and_charges - this.frm.doc.delivery_charges;
			this.set_in_company_currency(this.frm.doc, ["total_taxes", "delivery_charges"], !this.should_round_transaction_currency());
		}
	},

	calculate_gross_profit: function() {
		if (this.frm.doc.is_return) {
			return;
		}

		var me = this;

		if (this.frm.doc.doctype == 'Purchase Invoice') {
			this.frm.doc.total_revenue = 0;
			this.frm.doc.total_cogs = 0;
			me.frm.doc.total_source_sales_qty = 0;
			me.frm.doc.total_source_repack_qty = 0;
			me.frm.doc.total_source_reconciled_qty = 0;
			me.frm.doc.total_source_actual_qty = 0;
			me.frm.doc.total_repacked_actual_qty = 0;

			$.each(this.frm.doc.items || [], function (i, item) {
				item.source_batch_value = flt(item.source_purchase_cost) + flt(item.base_net_amount) + flt(item.source_lcv_cost);
				item.lc_rate = item.stock_qty ? flt(item.source_batch_value) / flt(item.stock_qty) : 0;

				item.repacked_batch_value = flt(item.lc_rate) * flt(item.source_repack_qty) + flt(item.repacked_additional_cost);
				item.repacked_cost_rate = item.repacked_repack_qty ? flt(item.repacked_batch_value) / flt(item.repacked_repack_qty) : 0;

				item.batch_cogs = flt(item.lc_rate) * (flt(item.source_sales_qty) - flt(item.source_reconciled_qty));
				item.batch_cogs += flt(item.repacked_cost_rate) * (flt(item.repacked_sales_qty) - flt(item.repacked_reconciled_qty));

				item.gross_profit = flt(item.batch_revenue) - flt(item.batch_cogs);
				item.per_gross_profit = item.batch_revenue ? flt(item.gross_profit) / flt(item.batch_revenue) * 100 : 0;

				item.repack_conversion_factor = item.repacked_repack_qty ? flt(item.source_repack_qty) / flt(item.repacked_repack_qty) : 0;
				item.qty_used_for_gp = flt(item.source_sales_qty) - flt(item.source_reconciled_qty);
				item.qty_used_for_gp += (flt(item.repacked_sales_qty) - flt(item.repacked_reconciled_qty)) * item.repack_conversion_factor;
				item.gross_profit_per_unit = item.gross_profit / item.qty_used_for_gp;

				me.frm.doc.total_revenue += item.batch_revenue;
				me.frm.doc.total_cogs += item.batch_cogs;

				me.frm.doc.total_source_sales_qty += item.source_sales_qty;
				me.frm.doc.total_source_repack_qty += item.source_repack_qty;
				me.frm.doc.total_source_reconciled_qty += item.source_reconciled_qty;
				me.frm.doc.total_source_actual_qty += item.source_actual_qty;
				me.frm.doc.total_repacked_actual_qty += item.repacked_actual_qty;
			});

			this.frm.doc.total_gross_profit = this.frm.doc.total_revenue - this.frm.doc.total_cogs;
			this.frm.doc.per_gross_profit = this.frm.doc.total_revenue ? this.frm.doc.total_gross_profit / this.frm.doc.total_revenue * 100 : 0;

			this.update_selected_item_gross_profit();

		} else if (["Sales Invoice", "Sales Order"].includes(this.frm.doc.doctype)) {
			this.frm.doc.total_revenue = 0;
			this.frm.doc.total_cogs = 0;

			$.each(this.frm.doc.items || [], function (i, item) {
				item.cogs_per_unit = flt(item.valuation_rate) * flt(item.conversion_factor);
				if (flt(item.alt_uom_size_std)) {
					item.cogs_per_unit *= flt(item.alt_uom_size) / flt(item.alt_uom_size_std);
				}

				item.revenue = item.base_net_amount - flt(item.base_returned_amount);
				item.cogs_qty = flt(item.qty) - flt(item.returned_qty);
				item.cogs = item.cogs_per_unit * item.cogs_qty;
				item.gross_profit = item.revenue - item.cogs;
				item.per_gross_profit = item.revenue ? item.gross_profit / item.revenue * 100 : 0;
				item.gross_profit_per_unit = item.cogs_qty ? item.gross_profit / item.cogs_qty : 0;

				if (item.cogs) {
					me.frm.doc.total_revenue += item.revenue;
					me.frm.doc.total_cogs += item.cogs;
				}
			});

			this.frm.doc.total_gross_profit = this.frm.doc.total_revenue - this.frm.doc.total_cogs;
			this.frm.doc.per_gross_profit = this.frm.doc.total_revenue ? this.frm.doc.total_gross_profit / this.frm.doc.total_revenue * 100 : 0;

			this.update_selected_item_gross_profit();

		} else if (this.frm.doc.doctype == "Purchase Order") {
			this.frm.doc.total_revenue = 0;
			this.frm.doc.total_cogs = 0;

			$.each(this.frm.doc.items || [], function (i, item) {
				item.cogs_per_unit = flt(item.landed_rate) * flt(item.conversion_factor);
				if (flt(item.alt_uom_size_std)) {
					item.cogs_per_unit *= flt(item.alt_uom_size) / flt(item.alt_uom_size_std);
				}

				item.revenue = flt(item.qty) * flt(item.conversion_factor) * flt(item.base_selling_price);
				item.cogs_qty = flt(item.qty);
				item.cogs = item.cogs_per_unit * item.cogs_qty;
				item.gross_profit = item.revenue - item.cogs;
				item.per_gross_profit = item.revenue ? item.gross_profit / item.revenue * 100 : 0;
				item.gross_profit_per_unit = item.cogs_qty ? item.gross_profit / item.cogs_qty : 0;

				if (item.cogs) {
					me.frm.doc.total_revenue += item.revenue;
					me.frm.doc.total_cogs += item.cogs;
				}
			});

			this.frm.doc.total_gross_profit = this.frm.doc.total_revenue - this.frm.doc.total_cogs;
			this.frm.doc.per_gross_profit = this.frm.doc.total_revenue ? this.frm.doc.total_gross_profit / this.frm.doc.total_revenue * 100 : 0

			this.update_selected_item_gross_profit();
		}
	},

	set_rounded_total: function() {
		var disable_rounded_total = 0;
		if(frappe.meta.get_docfield(this.frm.doc.doctype, "disable_rounded_total", this.frm.doc.name)) {
			disable_rounded_total = this.frm.doc.disable_rounded_total;
		} else if (frappe.sys_defaults.disable_rounded_total) {
			disable_rounded_total = frappe.sys_defaults.disable_rounded_total;
		}

		if (cint(disable_rounded_total) || !this.should_round_transaction_currency()) {
			this.frm.doc.rounded_total = 0;
			this.frm.doc.base_rounded_total = 0;
			return;
		}

		if(frappe.meta.get_docfield(this.frm.doc.doctype, "rounded_total", this.frm.doc.name)) {
			this.frm.doc.rounded_total = round_based_on_smallest_currency_fraction(this.frm.doc.grand_total,
				this.frm.doc.currency, precision("rounded_total"));
			this.frm.doc.rounding_adjustment += flt(this.frm.doc.rounded_total - this.frm.doc.grand_total,
				precision("rounding_adjustment"));

			this.set_in_company_currency(this.frm.doc, ["rounding_adjustment", "rounded_total"]);
		}
	},

	_cleanup: function() {
		this.frm.doc.base_in_words = this.frm.doc.in_words = "";

		if(this.frm.doc["items"] && this.frm.doc["items"].length) {
			if(!frappe.meta.get_docfield(this.frm.doc["items"][0].doctype, "item_tax_amount", this.frm.doctype)) {
				$.each(this.frm.doc["items"] || [], function(i, item) {
					delete item["item_tax_amount"];
				});
			}
		}

		if(this.frm.doc["taxes"] && this.frm.doc["taxes"].length) {
			var temporary_fields = ["tax_amount_for_current_item", "grand_total_for_current_item",
				"tax_fraction_for_current_item", "grand_total_fraction_for_current_item"];

			if(!frappe.meta.get_docfield(this.frm.doc["taxes"][0].doctype, "tax_amount_after_discount_amount", this.frm.doctype)) {
				temporary_fields.push("tax_amount_after_discount_amount");
			}

			$.each(this.frm.doc["taxes"] || [], function(i, tax) {
				$.each(temporary_fields, function(i, fieldname) {
					delete tax[fieldname];
				});

				tax.item_wise_tax_detail = JSON.stringify(tax.item_wise_tax_detail);
			});
		}
	},

	set_discount_amount: function() {
		if(this.frm.doc.additional_discount_percentage) {
			this.frm.doc.discount_amount = flt(flt(this.frm.doc[frappe.scrub(this.frm.doc.apply_discount_on)])
				* this.frm.doc.additional_discount_percentage / 100, precision("discount_amount"));
		}
	},

	apply_discount_amount: function() {
		var me = this;
		var distributed_amount = 0.0;
		this.frm.doc.base_discount_amount = 0.0;

		if (this.frm.doc.discount_amount) {
			if(!this.frm.doc.apply_discount_on)
				frappe.throw(__("Please select Apply Discount On"));

			this.frm.doc.base_discount_amount = flt(this.frm.doc.discount_amount * this.frm.doc.conversion_rate,
				precision("base_discount_amount"));

			var total_for_discount_amount = this.get_total_for_discount_amount();
			var net_total = 0;
			// calculate item amount after Discount Amount
			if (total_for_discount_amount) {
				$.each(this.frm.doc["items"] || [], function(i, item) {
					distributed_amount = flt(me.frm.doc.discount_amount) * item.net_amount / total_for_discount_amount;
					item.net_amount = flt(item.net_amount - distributed_amount,
						precision("base_amount", item));
					net_total += item.net_amount;

					// discount amount rounding loss adjustment if no taxes
					if ((!(me.frm.doc.taxes || []).length || total_for_discount_amount==me.frm.doc.net_total || (me.frm.doc.apply_discount_on == "Net Total"))
							&& i == (me.frm.doc.items || []).length - 1) {
						var discount_amount_loss = flt(me.frm.doc.net_total - net_total
							- me.frm.doc.discount_amount, precision("net_total"));
						item.net_amount = flt(item.net_amount + discount_amount_loss,
							precision("net_amount", item));
					}
					item.net_rate = item.qty ? flt(item.net_amount / item.qty, precision("net_rate", item)) : 0;
					me.set_in_company_currency(item, ["net_rate", "net_amount"]);
				});

				this.discount_amount_applied = true;
				this._calculate_taxes_and_totals();
			}
		}
	},

	get_total_for_discount_amount: function() {
		if(this.frm.doc.apply_discount_on == "Net Total") {
			return this.frm.doc.net_total;
		} else {
			var total_actual_tax = 0.0;
			var actual_taxes_dict = {};

			$.each(this.frm.doc["taxes"] || [], function(i, tax) {
				if (tax.charge_type == "Actual" || tax.charge_type == "Weighted Distribution") {
					var tax_amount = (tax.category == "Valuation") ? 0.0 : tax.tax_amount;
					tax_amount *= (tax.add_deduct_tax == "Deduct") ? -1.0 : 1.0;
					actual_taxes_dict[tax.idx] = tax_amount;
				} else if (actual_taxes_dict[tax.row_id] !== null) {
					var actual_tax_amount = flt(actual_taxes_dict[tax.row_id]) * flt(tax.rate) / 100;
					actual_taxes_dict[tax.idx] = actual_tax_amount;
				}
			});

			$.each(actual_taxes_dict, function(key, value) {
				if (value) total_actual_tax += value;
			});

			return flt(this.frm.doc.grand_total - total_actual_tax, precision("grand_total"));
		}
	},

	calculate_total_advance: function(update_paid_amount) {
		var total_allocated_amount = frappe.utils.sum($.map(this.frm.doc["advances"] || [], function(adv) {
			return flt(adv.allocated_amount, precision("allocated_amount", adv));
		}));
		this.frm.doc.total_advance = flt(total_allocated_amount, precision("total_advance"));

		this.calculate_outstanding_amount(update_paid_amount);
	},

	calculate_outstanding_amount: function(update_paid_amount) {
		// NOTE:
		// paid_amount and write_off_amount is only for POS/Loyalty Point Redemption Invoice
		// total_advance is only for non POS Invoice
		if(this.frm.doc.doctype == "Sales Invoice" && this.frm.doc.is_return){
			this.calculate_paid_amount();
		}

		if(this.frm.doc.is_return || this.frm.doc.docstatus > 0) return;

		if (this.should_round_transaction_currency()) {
			frappe.model.round_floats_in(this.frm.doc, ["grand_total", "total_advance", "write_off_amount"]);
		}

		if(in_list(["Sales Invoice", "Purchase Invoice"], this.frm.doc.doctype)) {
			var grand_total = this.frm.doc.rounded_total || this.frm.doc.grand_total;

			if(this.frm.doc.party_account_currency == this.frm.doc.currency) {
				var total_amount_to_pay = flt((grand_total - this.frm.doc.total_advance
					- this.frm.doc.write_off_amount), precision("grand_total"));
			} else {
				var total_amount_to_pay = flt(
					(flt(grand_total*this.frm.doc.conversion_rate, precision("grand_total"))
						- this.frm.doc.total_advance - this.frm.doc.base_write_off_amount),
					precision("base_grand_total")
				);
			}

			frappe.model.round_floats_in(this.frm.doc, ["paid_amount"]);
			this.set_in_company_currency(this.frm.doc, ["paid_amount"]);

			if(this.frm.refresh_field){
				this.frm.refresh_field("paid_amount");
				this.frm.refresh_field("base_paid_amount");
			}

			if(this.frm.doc.doctype == "Sales Invoice") {
				let total_amount_for_payment = (this.frm.doc.redeem_loyalty_points && this.frm.doc.loyalty_amount)
					? flt(total_amount_to_pay - this.frm.doc.loyalty_amount, precision("base_grand_total"))
					: total_amount_to_pay;
				this.set_default_payment(total_amount_for_payment, update_paid_amount);
				this.calculate_paid_amount();
			}
			this.calculate_change_amount();

			var paid_amount = (this.frm.doc.party_account_currency == this.frm.doc.currency) ?
				this.frm.doc.paid_amount : this.frm.doc.base_paid_amount;
			this.frm.doc.outstanding_amount =  flt(total_amount_to_pay - flt(paid_amount) +
				flt(this.frm.doc.change_amount * this.frm.doc.conversion_rate), precision("outstanding_amount"));
		}
	},

	set_default_payment: function(total_amount_to_pay, update_paid_amount){
		var me = this;
		var payment_status = true;
		if(this.frm.doc.is_pos && (update_paid_amount===undefined || update_paid_amount)){
			$.each(this.frm.doc['payments'] || [], function(index, data){
				if(data.default && payment_status && total_amount_to_pay > 0) {
					data.base_amount = flt(total_amount_to_pay, precision("base_amount"));
					data.amount = flt(total_amount_to_pay / me.frm.doc.conversion_rate, precision("amount"));
					payment_status = false;
				}else if(me.frm.doc.paid_amount){
					data.amount = 0.0;
				}
			});
		}
	},

	calculate_paid_amount: function(){
		var me = this;
		var paid_amount = 0.0;
		var base_paid_amount = 0.0;
		if(this.frm.doc.is_pos) {
			$.each(this.frm.doc['payments'] || [], function(index, data){
				data.base_amount = flt(data.amount * me.frm.doc.conversion_rate, precision("base_amount"));
				paid_amount += data.amount;
				base_paid_amount += data.base_amount;
			});
		} else if(!this.frm.doc.is_return){
			this.frm.doc.payments = [];
		}
		if (this.frm.doc.redeem_loyalty_points && this.frm.doc.loyalty_amount) {
			base_paid_amount += this.frm.doc.loyalty_amount;
			paid_amount += flt(this.frm.doc.loyalty_amount / me.frm.doc.conversion_rate, precision("paid_amount"));
		}

		this.frm.doc.paid_amount = flt(paid_amount, precision("paid_amount"));
		this.frm.doc.base_paid_amount = flt(base_paid_amount, precision("base_paid_amount"));
	},

	calculate_change_amount: function(){
		this.frm.doc.change_amount = 0.0;
		this.frm.doc.base_change_amount = 0.0;
		if(this.frm.doc.doctype == "Sales Invoice"
			&& this.frm.doc.paid_amount > this.frm.doc.grand_total && !this.frm.doc.is_return) {

			var payment_types = $.map(this.frm.doc.payments, function(d) { return d.type; });
			if (in_list(payment_types, 'Cash')) {
				var grand_total = this.frm.doc.rounded_total || this.frm.doc.grand_total;
				var base_grand_total = this.frm.doc.base_rounded_total || this.frm.doc.base_grand_total;

				this.frm.doc.change_amount = flt(this.frm.doc.paid_amount - grand_total +
					this.frm.doc.write_off_amount, precision("change_amount"));

				this.frm.doc.base_change_amount = flt(this.frm.doc.base_paid_amount -
					base_grand_total + this.frm.doc.base_write_off_amount,
					precision("base_change_amount"));
			}
		}
	},

	calculate_write_off_amount: function(){
		if(this.frm.doc.paid_amount > this.frm.doc.grand_total){
			this.frm.doc.write_off_amount = flt(this.frm.doc.grand_total - this.frm.doc.paid_amount
				+ this.frm.doc.change_amount, precision("write_off_amount"));

			this.frm.doc.base_write_off_amount = flt(this.frm.doc.write_off_amount * this.frm.doc.conversion_rate,
				precision("base_write_off_amount"));
		}else{
			this.frm.doc.paid_amount = 0.0;
		}
		this.calculate_outstanding_amount(false);
	}
});
