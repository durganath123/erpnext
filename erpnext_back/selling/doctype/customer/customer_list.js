frappe.listview_settings['Customer'] = {
	add_fields: ["customer_name", "territory", "customer_group", "customer_type", "image", "disabled"],
	
	onload: function(listview) {
		var method = "erpnext.customer.enableDisableOrder";

		listview.page.add_menu_item(__("Enabled"), function() {
			listview.call_for_selected_items(method, {"disabled":"0"});
		});

		listview.page.add_menu_item(__("Disabled"), function() {
			listview.call_for_selected_items(method, {"disabled":"1"});
		});



	},
};
