# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc('stock', 'doctype', 'batch')

	frappe.db.sql("""
		update tabBatch b
		inner join tabItem i on i.name = b.item
		set b.item_name = i.item_name, b.item_group = i.item_group
	""")