// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

// js inside blog page

// shopping cart
frappe.provide("erpnext.shopping_cart");
var shopping_cart = erpnext.shopping_cart;

frappe.ready(function() {
	$(".cart-icon").hide();
	shopping_cart.quotation_name = frappe.utils.get_url_arg("name");
	shopping_cart.create_fields();
	shopping_cart.bind_events();
	shopping_cart.update_action_buttons();
	window.zoom_item_image(".cart-items",".cart-product-image", "data-item-image");
});

$.extend(shopping_cart, {
	create_fields: function() {
		shopping_cart.field_group = new frappe.ui.FieldGroup({
			parent: $('#cart-fields'),
			fields: [
				{
					label: __('Delivery Date'),
					fieldname: 'delivery_date',
					fieldtype: 'Date',
					reqd: 1,
					onchange: shopping_cart.handle_change_delivery_date
				},
				{
					label: __('Day'),
					fieldname: 'day',
					fieldtype: 'Data',
					read_only: 1
				},
				{
					fieldtype: 'Column Break'
				},
				{
					label: __('Customer Name'),
					fieldname: 'customer_name',
					fieldtype: 'Data',
					read_only: 1
				},
				{
					label: __('Contact'),
					fieldname: 'contact_display',
					fieldtype: 'Data',
					read_only: 1
				},
				{
					fieldtype: 'Column Break'
				},
				{
					label: __('Credit Limit'),
					fieldname: 'credit_limit',
					fieldtype: 'Currency',
					read_only: 1
				},
				{
					label: __('Balance Amount'),
					fieldname: 'customer_balance',
					fieldtype: 'Currency',
					read_only: 1
				}
			]
		});
		shopping_cart.field_group.make();

		let values = {};
		$(`.cart-field-data`).each(function (i, e) {
			let $this = $(this);
			values[$this.data('fieldname')] = $this.text();
		});
		frappe.run_serially([
			() => shopping_cart.ignore_update = true,
			() => shopping_cart.field_group.set_values(values),
			() => shopping_cart.ignore_update = false
		]);
	},

	bind_events: function () {
		shopping_cart.bind_address_select();
		shopping_cart.bind_place_order();
		shopping_cart.bind_change_qty();
		shopping_cart.bind_click_qty();
		shopping_cart.bind_qty_arrow_keys();
		shopping_cart.bind_change_uom();
		shopping_cart.bind_get_default_items();
		shopping_cart.bind_add_items();
		shopping_cart.bind_remove_cart_item();
	},

	cart_page_update_callback: function(r) {
		if(!r.exc) {
			$(".cart-icon").hide();

			$(".cart-items").html(r.message.items);
			$(".cart-tax-items").html(r.message.taxes);

			if (r.message.quotation_fields.delivery_date) {
				$("#cart-body").removeClass('hidden');
			} else {
				$("#cart-body").addClass('hidden');
			}

			shopping_cart.confirmed_by_customer = r.message.confirmed_by_customer;
			shopping_cart.update_action_buttons();

			frappe.run_serially([
				() => shopping_cart.ignore_update = true,
				() => shopping_cart.field_group.set_values(r.message.quotation_fields || {}),
				() => shopping_cart.ignore_update = false
			]);
		}
	},

	update_action_buttons() {
		if (shopping_cart.confirmed_by_customer) {
			$(".btn-place-order").hide();
			$(".btn-cancel-order").show();
		} else {
			$(".btn-place-order").show();
			$(".btn-cancel-order").hide();
		}
	},

	bind_get_default_items: function () {
		$('.btn-get-default-items').click(function () {
			var item_group = $(this).attr("data-item-group");
			shopping_cart.add_default_items({
				item_group: item_group,
				callback: shopping_cart.cart_page_update_callback,
				with_items: 1,
				name: shopping_cart.quotation_name,
				btn: this
			});
		});

	},

	bind_add_items: function () {
		$('.btn-add-items').click(function () {
			window.add_item_dialog(item_code => shopping_cart.add_item({
				item_code: item_code,
				callback: shopping_cart.cart_page_update_callback,
				with_items: 1,
				name: shopping_cart.quotation_name
			}));
		});
	},

	handle_change_delivery_date: function() {
		var delivery_date = shopping_cart.field_group.get_value('delivery_date') || "";
		shopping_cart.set_weekday(delivery_date);
		shopping_cart.update_cart_field({
			fieldname: 'delivery_date',
			value: delivery_date,
			with_items: 1,
			name: shopping_cart.quotation_name,
			callback: function (r) {
				shopping_cart.cart_page_update_callback(r);
			},
			freeze: 1
		});
	},

	set_weekday: function(delivery_date) {
		if (delivery_date) {
			var date_obj = moment(delivery_date);
			shopping_cart.field_group.set_value("day", date_obj.format("dddd"));
		} else {
			shopping_cart.field_group.set_value("day", "");
		}
	},

	bind_address_select: function() {
		$(".cart-addresses").on('click', '.address-card', function(e) {
			const $card = $(e.currentTarget);
			const address_type = $card.closest('[data-address-type]').attr('data-address-type');
			const address_name = $card.closest('[data-address-name]').attr('data-address-name');
			return frappe.call({
				type: "POST",
				method: "erpnext.shopping_cart.cart.update_cart_address",
				freeze: true,
				args: {
					address_type,
					address_name,
					name: shopping_cart.quotation_name
				},
				callback: function(r) {
					if(!r.exc) {
						$(".cart-tax-items").html(r.message.taxes);
					}
				}
			});
		});
	},

	bind_place_order: function() {
		$(".btn-place-order").on("click", function() {
			shopping_cart.place_order(1, this);
		});
		$(".btn-cancel-order").on("click", function() {
			shopping_cart.place_order(0, this);
		});
	},

	bind_change_qty: function() {
		// bind update button
		$(".cart-items").on("change", ".cart-qty", function() {
			var item_code = $(this).attr("data-item-code");
			var val = strip($(this).val());
			var newVal = parseInt(val);

			if (isNaN(newVal)) {
				frappe.msgprint(__("<b>{0}</b> is not a valid number", [val]));
				return false;
			}

			shopping_cart.update_cart_item({
				item_code: item_code,
				fieldname: 'qty',
				value: newVal,
				with_items: 1,
				name: shopping_cart.quotation_name,
				callback: function (r) {
					let focused_item_code = $('.cart-qty:focus').attr("data-item-code");

					shopping_cart.cart_page_update_callback(r);

					if (focused_item_code) {
						$(`.cart-qty[data-item-code='${focused_item_code}']`).focus();
					}
				},
				freeze: 1
			});
		});
	},

	bind_click_qty: function() {
		$(".cart-items").on("focus", "input.cart-qty", function() {
			$(this).select();
		});
	},

	bind_qty_arrow_keys: function() {
		$(".cart-items").on('keydown', "input.cart-qty", function(e) {
			window.handle_up_down_arrow_key(e, this, "input.cart-qty");
		});
	},

	bind_remove_cart_item: function() {
		$(".cart-items").on('click', '.remove-cart-item', function(){
			var item_code = $(this).attr('data-item-code');
			shopping_cart.update_cart_item({
				item_code: item_code,
				fieldname: 'qty',
				value: 0,
				with_items: 1,
				name: shopping_cart.quotation_name,
				callback: function (r) {
					shopping_cart.cart_page_update_callback(r);
				},
				freeze: 1
			});
		});
	},

	bind_change_uom: function() {
		$(".cart-items").on("change", ".cart-uom", function() {
			var item_code = $(this).attr("data-item-code");
			var newVal = $(this).val();

			shopping_cart.update_cart_item({
				item_code: item_code,
				fieldname: 'uom',
				value: newVal,
				with_items: 1,
				name: shopping_cart.quotation_name,
				callback: function (r) {
					shopping_cart.cart_page_update_callback(r);
				},
				freeze: 1
			});
		});
	},

	render_tax_row: function($cart_taxes, doc, shipping_rules) {
		var shipping_selector;
		if(shipping_rules) {
			shipping_selector = '<select class="form-control">' + $.map(shipping_rules, function(rule) {
				return '<option value="' + rule[0] + '">' + rule[1] + '</option>' }).join("\n") +
			'</select>';
		}

		var $tax_row = $(repl('<div class="row">\
			<div class="col-md-9 col-sm-9">\
				<div class="row">\
					<div class="col-md-9 col-md-offset-3">' +
					(shipping_selector || '<p>%(description)s</p>') +
					'</div>\
				</div>\
			</div>\
			<div class="col-md-3 col-sm-3 text-right">\
				<p' + (shipping_selector ? ' style="margin-top: 5px;"' : "") + '>%(formatted_tax_amount)s</p>\
			</div>\
		</div>', doc)).appendTo($cart_taxes);

		if(shipping_selector) {
			$tax_row.find('select option').each(function(i, opt) {
				if($(opt).html() == doc.description) {
					$(opt).attr("selected", "selected");
				}
			});
			$tax_row.find('select').on("change", function() {
				shopping_cart.apply_shipping_rule($(this).val(), this);
			});
		}
	},

	apply_shipping_rule: function(rule, btn) {
		return frappe.call({
			btn: btn,
			type: "POST",
			method: "erpnext.shopping_cart.cart.apply_shipping_rule",
			args: {
				shipping_rule: rule,
				name: shopping_cart.quotation_name
			},
			callback: function(r) {
				if(!r.exc) {
					shopping_cart.render(r.message);
				}
			}
		});
	},

	place_order: function(confirmed, btn) {
		shopping_cart.call_cart_method("erpnext.shopping_cart.cart.place_order", {
			confirmed: confirmed,
			name: shopping_cart.quotation_name,
			with_items: 1,
		}, {
			btn: btn,
			override_callback: 1,
			callback: function (r) {
				if (r.exc) {
					return;
				}

				if (r.message.failed) {
					shopping_cart.set_cart_messages(r);
				} else {
					shopping_cart.update_cart_callback(r);
					shopping_cart.cart_page_update_callback(r);
					if (confirmed) {
						window.location.href = "/purchase-orders/" + encodeURIComponent(r.message.name);
					}
				}
			}
		});
	}
});

function show_terms() {
	var html = $(".cart-terms").html();
	frappe.msgprint(html);
}
