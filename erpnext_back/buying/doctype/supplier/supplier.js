// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Supplier", {
	setup: function (frm) {
		frm.set_query('default_price_list', { 'buying': 1 });
		if (frm.doc.__islocal == 1) {
			frm.set_value("represents_company", "");
		}
		frm.set_query('account', 'accounts', function (doc, cdt, cdn) {
			var d = locals[cdt][cdn];
			return {
				filters: {
					'account_type': 'Payable',
					'company': d.company,
					"is_group": 0
				}
			}
		});

		frm.set_query('expense_account', function() {
			return {
				filters:[
					['Account', 'is_group', '=', 0],
					['Account', 'account_type', 'in', ['Expense Account', 'Cost of Goods Sold']]
				]
			};
		});

		frm.set_query("default_bank_account", function() {
			return {
				filters: {
					"is_company_account":1
				}
			}
		});
	},
	refresh: function (frm) {
		frappe.dynamic_link = { doc: frm.doc, fieldname: 'name', doctype: 'Supplier' }

		if (frappe.defaults.get_default("supp_master_name") != "Naming Series") {
			frm.toggle_display("naming_series", false);
		} else {
			erpnext.toggle_naming_series();
		}

		if (frm.doc.__islocal) {
			hide_field(['address_html','contact_html']);
			frappe.contacts.clear_address_and_contact(frm);
		}
		else {
			unhide_field(['address_html','contact_html']);
			frappe.contacts.render_address_and_contact(frm);

			// custom buttons
			frm.add_custom_button(__('Accounting Ledger'), function () {
				frappe.set_route('query-report', 'General Ledger',
					{ party_type: 'Supplier', party: frm.doc.name });
			}, __("View"));

			frm.add_custom_button(__('Accounts Payable'), function () {
				frappe.set_route('query-report', 'Accounts Payable', { supplier: frm.doc.name });
			}, __("View"));

			frm.add_custom_button(__('Bank Account'), function () {
				erpnext.utils.make_bank_account(frm.doc.doctype, frm.doc.name);
			}, __('Create'));

			frm.add_custom_button(__('Pricing Rule'), function () {
				erpnext.utils.make_pricing_rule(frm.doc.doctype, frm.doc.name);
			}, __('Create'));

			// indicators
			erpnext.utils.set_party_dashboard_indicators(frm);
		}
	},

	is_internal_supplier: function(frm) {
		if (frm.doc.is_internal_supplier == 1) {
			frm.toggle_reqd("represents_company", true);
		}
		else {
			frm.toggle_reqd("represents_company", false);
		}
	},

	default_currency: function (frm) {
		const default_company = frappe.defaults.get_default('company');
		if (frm.doc.default_currency && default_company) {
			frappe.db.get_list("Account", {
				fields: 'name',
				filters: {
					account_type: "Payable",
					account_currency: frm.doc.default_currency,
					company: default_company,
					is_group: 0
				}
			}).then(function (message) {
				if (message && message.length == 1) {
					var default_company_account = frm.doc.accounts.filter(d => d.company == default_company);

					if (default_company_account.length) {
						$.each(default_company_account || [], function (i, d) {
							frappe.model.set_value(d.doctype, d.name, 'account', message[0].name);
						});
					} else {
						frm.add_child('accounts', {'company': default_company, 'account': message[0].name});
						frm.refresh_fields('accounts');
					}
				}
			});
		}
	}
});
