# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	to_update = frappe.db.sql_list("""
		select distinct so_item.prevdoc_docname
		from `tabSales Order Item` so_item
		inner join `tabQuotation` q on q.name = so_item.prevdoc_docname
		where ifnull(so_item.prevdoc_docname, '') != '' and q.docstatus = 1
	""")

	for name in to_update:
		frappe.get_doc("Quotation", name).set_status(update=True)
