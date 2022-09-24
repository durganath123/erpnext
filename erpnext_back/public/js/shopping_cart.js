// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

// shopping cart
frappe.provide("erpnext.shopping_cart");
var shopping_cart = erpnext.shopping_cart;

frappe.ready(function() {
	var full_name = frappe.session && frappe.session.user_fullname;
	// update user
	if(full_name) {
		$('.navbar li[data-label="User"] a')
			.html('<i class="fa fa-fixed-width fa fa-user"></i> ' + full_name);
	}

	// update login
	shopping_cart.show_shoppingcart_dropdown();
	shopping_cart.set_cart_count();
	shopping_cart.bind_dropdown_cart_buttons();
});

$.extend(shopping_cart, {
	cart_update_callbacks: [],
	cart_update_doc_callbacks: [],
	cart_update_item_callbacks: [],

	check_if_logged_in: function() {
		if(frappe.session.user==="Guest") {
			if(localStorage) {
				localStorage.setItem("last_visited", window.location.pathname);
			}
			window.location.href = "/login";
			return false;
		}
		return true;
	},

	set_cart_count: function() {
		var $cart = $('.cart-icon');
		var $badge = $cart.find("#cart-count");
		var cart_count = frappe.get_cookie("cart_count");
		var to_show = true;

		if(frappe.session.user==="Guest") {
			cart_count = 0;
			to_show = false;
		}

		$(".shopping-cart").toggleClass('hidden', !to_show);
		$cart.css("display", to_show ? "inline" : "none");

		if(cart_count) {
			$badge.html(cart_count);
		} else {
			$badge.remove();
		}
	},

	call_cart_method: function(method, args, opts) {
		if(shopping_cart.in_update || shopping_cart.ignore_update || !shopping_cart.check_if_logged_in()) {
			return;
		}
		if(!opts) {
			opts = {};
		}

		shopping_cart.in_update = true;
		return frappe.call({
			type: "POST",
			method: method,
			args: args,
			btn: opts.btn,
			freeze: opts.freeze || 1,
			callback: function(r) {
				if (!opts.override_callback) {
					shopping_cart.update_cart_callback(r, opts);
				}
				if(opts.callback)
					opts.callback(r);
			},
			always: function() {
				shopping_cart.in_update = false;
				if (opts.always)
					opts.always();
			}
		});
	},

	update_cart_callback: function(r, opts) {
		if (!opts) {
			opts = {};
		}

		if(!r.exc) {
			shopping_cart.set_cart_count();

			if (r.message.shopping_cart_menu) {
				shopping_cart.set_shopping_cart_menu(r.message.shopping_cart_menu);
			}

			$(".cart-indicator").html(r.message.indicator || "");
			shopping_cart.set_cart_messages(r);

			$.each(shopping_cart.cart_update_callbacks || [], (i, callback) => callback(r, opts));
			if (opts.item_code) {
				$.each(shopping_cart.cart_update_item_callbacks || [], (i, callback) => callback(r, opts));
			} else {
				$.each(shopping_cart.cart_update_doc_callbacks || [], (i, callback) => callback(r, opts));
			}
		}
	},

	set_cart_messages: function(r) {
		$(".cart-warning").html(r.message.warnings || "");
		$(".cart-error").html(r.message.errors || "");
	},

	update_cart_item: function(opts) {
		if (!opts || !opts.item_code || !opts.fieldname || opts.value == null) {
			return;
		}

		shopping_cart.call_cart_method("erpnext.shopping_cart.cart.update_cart_item", {
			item_code: opts.item_code,
			fieldname: opts.fieldname,
			value: opts.value,
			with_items: opts.with_items || 0,
			name: opts.name
		}, opts);
	},

	update_cart_field: function(opts) {
		if (!opts || !opts.fieldname || !opts.value) {
			return;
		}

		shopping_cart.call_cart_method("erpnext.shopping_cart.cart.update_cart_field", {
			fieldname: opts.fieldname,
			value: opts.value,
			with_items: opts.with_items || 0,
			name: opts.name
		}, opts);
	},

	add_item: function(opts) {
		if (!opts || !opts.item_code) {
			return;
		}

		shopping_cart.call_cart_method("erpnext.shopping_cart.cart.add_item", {
			item_code: opts.item_code,
			with_items: opts.with_items || 0,
			name: opts.name
		}, opts);
	},

	add_default_items: function(opts) {
		if (!opts) {
			opts = {};
		}

		shopping_cart.call_cart_method("erpnext.shopping_cart.cart.get_default_items", {
			item_group: opts.item_group || "",
			with_items: opts.with_items || 0,
			name: opts.name
		}, opts);
	},

	copy_items_from_transaction: function(opts) {
		if (!opts || !opts.dt || !opts.dn) {
			return;
		}

		shopping_cart.call_cart_method("erpnext.shopping_cart.cart.copy_items_from_transaction", {
			dt: opts.dt,
			dn: opts.dn,
			with_items: opts.with_items || 0,
		}, opts);
	},

	show_shoppingcart_dropdown: function() {
		$(".shopping-cart").on('shown.bs.dropdown', function() {
			if (!$('.shopping-cart-menu .cart-container').length) {
				return frappe.call({
					method: 'erpnext.shopping_cart.cart.get_shopping_cart_menu',
					callback: function(r) {
						if (r.message) {
							shopping_cart.set_shopping_cart_menu(r.message);
						}
					}
				});
			}
		});
	},

	set_shopping_cart_menu: function(html) {
		$('.shopping-cart-menu').html(html);
	},

	bind_dropdown_cart_buttons: function () {
		$(".cart-icon").on('click', '.number-spinner button', function () {
			var btn = $(this),
				input = btn.closest('.number-spinner').find('input'),
				oldValue = input.val().trim(),
				newVal = 0;

			if (btn.attr('data-dir') == 'up') {
				newVal = parseInt(oldValue) + 1;
			} else {
				if (parseInt(oldValue) >= 1) {
					newVal = parseInt(oldValue) - 1;
				}
			}

			input.val(newVal);
			var item_code = input.attr("data-item-code");

			shopping_cart.update_cart_item({
				item_code: item_code,
				fieldname: 'qty',
				value: newVal,
				btn: btn,
				freeze: 1
			});

			return false;
		});

	},

});
