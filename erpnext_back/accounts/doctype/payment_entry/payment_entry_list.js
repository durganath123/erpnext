frappe.listview_settings['Payment Entry'] = {
	onload: function(listview) {
		listview.page.add_menu_item(__("Receive"), function() {
			frappe.route_options = {
					"payment_type": "Receive",
					"party_type": "Customer",
					"naming_series": "PR-",
				};
			var	tn = frappe.model.make_new_doc_and_get_name("Payment Entry");
				frappe.set_route("Form", "Payment Entry", tn);
		});

		listview.page.add_menu_item(__("Pay"), function() {
			frappe.route_options = {
					"payment_type": "Pay",
					"party_type": "Supplier",
					"naming_series": "PE-",
				};
			var	tn = frappe.model.make_new_doc_and_get_name("Payment Entry");
				frappe.set_route("Form", "Payment Entry", tn);
		});

		listview.page.add_menu_item(__("Internal Transfer"), function() {
			frappe.route_options = {
					"payment_type": "Internal Transfer",
					"party_type": "",
					"naming_series": "PE-",
				};
			var	tn = frappe.model.make_new_doc_and_get_name("Payment Entry");
				frappe.set_route("Form", "Payment Entry", tn);
		});


	},
};
