# Copyright (c) 2017, Frappe and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc("stock", "doctype", "stock_settings")

	frappe.db.set_value("Stock Settings", None, {
		"force_set_selling_item_prices": 1,
	}, None, update_modified=False)
