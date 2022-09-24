# Copyright (c) 2017, Frappe and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc("stock", "doctype", "stock_settings")

	frappe.db.set_value("Stock Settings", None, {
		"update_buying_prices_on_submission_of_purchase_order": 1,
		"get_prices_based_on_date": "Delivery Date",
		"stale_price_days": 14
	}, None, update_modified=False)
