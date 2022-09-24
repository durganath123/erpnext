# Copyright (c) 2017, Frappe and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe


def execute():
	for company in frappe.get_all("Company"):
		acc_frozen_upto = frappe.db.get_value("Accounts Settings", None, "acc_frozen_upto")
		stock_adjustment_account = frappe.db.get_value("Company", company.name, "stock_adjustment_account")
		if not stock_adjustment_account:
			continue

		date_condition = " and p.posting_date > {0}".format(frappe.db.escape(acc_frozen_upto)) if acc_frozen_upto else ""
		stock_entries = frappe.db.sql_list("""
			select distinct p.name
			from `tabStock Entry Detail` d, `tabStock Entry` p
			where p.name = d.parent and p.purpose = 'Repack' and d.expense_account != %s and d.docstatus=1 {0}
		""".format(date_condition), stock_adjustment_account)

		for name in stock_entries:
			doc = frappe.get_doc("Stock Entry", name)
			for d in doc.items:
				if d.expense_account != stock_adjustment_account:
					d.expense_account = stock_adjustment_account
					d.db_update()

			doc.docstatus = 2
			doc.make_gl_entries_on_cancel(repost_future_gle=False)
			doc.docstatus = 1
			doc.make_gl_entries(repost_future_gle=False)
