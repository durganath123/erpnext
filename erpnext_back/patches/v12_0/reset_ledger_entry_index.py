# Copyright (c) 2020, Frappe and Contributors
# License: GNU General Public License v3. See license.txt

import frappe


def execute():
	frappe.reload_doc("stock", "doctype", "stock_ledger_entry")

	if frappe.db.has_index('tabStock Ledger Entry', 'posting_sort_index'):
		frappe.db.commit()
		frappe.db.sql("drop index posting_sort_index on `tabStock Ledger Entry`")

	from erpnext.stock.doctype.stock_ledger_entry.stock_ledger_entry import on_doctype_update
	on_doctype_update()
