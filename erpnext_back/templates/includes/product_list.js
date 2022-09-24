// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

window.get_product_list = function() {
	$(".more-btn .btn").click(function() {
		window.get_product_list()
	});

	if(window.start==undefined) {
		throw "product list not initialized (no start)"
	}

	$.ajax({
		method: "GET",
		url: "/",
		data: {
			cmd: "erpnext.templates.pages.product_search.get_product_list",
			start: window.start,
			search: window.search,
			product_group: window.product_group
		},
		dataType: "json",
		success: function(data) {
			window.render_product_list(data.message || []);
		}
	})
}

window.render_product_list = function(data) {
	var table = $("#search-list .table");
	if(data.length) {
		if(!table.length)
			var table = $("<table class='table'>").appendTo("#search-list");

		$.each(data, function(i, d) {
			$(d).appendTo(table);
		});
	}
	if(data.length < 10) {
		if(!table) {
			$(".more-btn")
				.replaceWith("<div class='alert alert-warning'>{{ _("No products found.") }}</div>");
		} else {
			$(".more-btn")
				.replaceWith("<div class='text-muted'>{{ _("Nothing more to show.") }}</div>");
		}
	} else {
		$(".more-btn").toggle(true)
	}
	window.start += (data.length || 0);
}

window.add_item_dialog = function(callback) {
	var dialog = new frappe.ui.Dialog({
		data: [],
		has_variant: 1,
		title: __("Add Items"), fields: [
			{label: __("Search"), fieldname: "search", fieldtype: "Data"},
			{fieldname: "body", fieldtype: "HTML"}
		]
	});
	dialog.set_primary_action(__("Search"), () => window.product_list_dialog.call(this, dialog, callback));
	dialog.show();
}

window.product_list_dialog = function(dialog, callback) {
	return frappe.call({
		type: "POST",
		method: "erpnext.templates.pages.product_search.get_product_list",
		freeze: true,
		args: {
			search: dialog.get_value('search'),
			variants_only: dialog.has_variant
		},
		callback: function (r) {
			if (r.message && r.message.length) {
				dialog.fields_dict.body.$wrapper.html(r.message.join(""));

				$('.product-link', dialog.$wrapper).click(function() {
					var item_code = $(this).attr('data-item-code');
					callback(item_code);
					dialog.hide();
					return false;
				});
			} else {
				dialog.fields_dict.body.$wrapper.html("No items found");
			}
			
		}

	});
}

window.handle_up_down_arrow_key = function(event, target, selector) {
	let prev = null;
	const elements = $(selector);

	elements.each(function(i) {
		if (this == target) {
			if (event.keyCode == 38 && prev) { // Up
				$(prev).focus();
				event.preventDefault();
				return false;
			} else if (event.keyCode == 40 && i+1 < elements.length) { // Down
				$(elements[i+1]).focus();
				event.preventDefault();
				return false;
			}
		}

		prev = this;
	});
};