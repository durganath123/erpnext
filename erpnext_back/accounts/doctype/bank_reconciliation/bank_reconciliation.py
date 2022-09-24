# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt, getdate, nowdate, fmt_money
from frappe import msgprint, _
from frappe.model.document import Document

form_grid_templates = {
	"journal_entries": "templates/form_grid/bank_reconciliation_grid.html"
}

class BankReconciliation(Document):
	def get_payment_entries(self):
		if not (self.bank_account):
			msgprint("Bank Account is Mandatory")
			return

		condition = ""
		if not self.include_reconciled_entries:
			condition = " and (clearance_date is null or clearance_date='0000-00-00')"
		if self.from_date:
			condition += " and posting_date >= %(from)s"
		if self.to_date:
			condition += " and posting_date <= %(to)s"

		journal_entries = frappe.db.sql("""
			select 
				"Journal Entry" as payment_document, t1.name as payment_entry, t1.pay_to_recd_from as pay_to_recd_from, 
				t1.cheque_no as cheque_number, t1.cheque_date, 
				t2.debit_in_account_currency as debit, t2.credit_in_account_currency as credit, 
				t1.posting_date, t2.against_account, t1.clearance_date, t2.account_currency 
			from
				`tabJournal Entry` t1, `tabJournal Entry Account` t2
			where
				t2.parent = t1.name and t2.account = %(account)s and t1.docstatus=1
				and ifnull(t1.is_opening, 'No') = 'No' {0}
			order by t1.posting_date ASC, t1.name DESC
		""".format(condition), {
			"account": self.bank_account,
			"from": self.from_date,
			"to": self.to_date
		}, as_dict=1)

		payment_entries = frappe.db.sql("""
			select 
				"Payment Entry" as payment_document, name as payment_entry, party as pay_to_recd_from,  
				reference_no as cheque_number, reference_date as cheque_date, 
				if(paid_from=%(account)s, paid_amount, "") as credit, 
				if(paid_from=%(account)s, "", received_amount) as debit, 
				posting_date, ifnull(party,if(paid_from=%(account)s,paid_to,paid_from)) as against_account, clearance_date,
				if(paid_to=%(account)s, paid_to_account_currency, paid_from_account_currency) as account_currency
			from `tabPayment Entry`
			where
				(paid_from=%(account)s or paid_to=%(account)s) and docstatus=1 {0}
			order by 
				posting_date ASC, name DESC
		""".format(condition),
		        {"account":self.bank_account, "from":self.from_date, "to":self.to_date}, as_dict=1)

		pos_entries = []
		if self.include_pos_transactions:
			pos_entries = frappe.db.sql("""
				select
					"Sales Invoice Payment" as payment_document, sip.name as payment_entry, sip.amount as debit,
					si.posting_date, si.debit_to as against_account, sip.clearance_date,
					account.account_currency, 0 as credit
				from `tabSales Invoice Payment` sip, `tabSales Invoice` si, `tabAccount` account
				where
					sip.account=%(account)s and si.docstatus=1 and sip.parent = si.name
					and account.name = sip.account {0}
				order by
					si.posting_date ASC, si.name DESC
			""".format(condition),
			        {"account":self.bank_account, "from":self.from_date, "to":self.to_date}, as_dict=1)

		entries = sorted(list(payment_entries)+list(journal_entries+list(pos_entries)),
			key=lambda k: k['cheque_date'] or k['posting_date'] or getdate(nowdate()))

		self.set('payment_entries', [])
		self.total_amount = 0.0

		for d in entries:
			row = self.append('payment_entries', {})
			amount = d.debit if d.debit else d.credit
			d.amount = fmt_money(amount, 2, d.account_currency)
			d.pop("credit")
			d.pop("debit")
			d.pop("account_currency")
			row.update(d)
			self.total_amount += flt(amount)

	def update_clearance_date(self):
		clearance_date_updated = False
		for d in self.get('payment_entries'):
			if d.clearance_date:
				if not d.payment_document:
					frappe.throw(_("Row #{0}: Payment document is required to complete the trasaction"))

				if d.cheque_date and getdate(d.clearance_date) < getdate(d.cheque_date):
					frappe.throw(_("Row #{0}: Clearance date {1} cannot be before Cheque Date {2}")
						.format(d.idx, d.clearance_date, d.cheque_date))

			if d.clearance_date or self.include_reconciled_entries:
				if not d.clearance_date:
					d.clearance_date = None

				prev_clearance_date = frappe.db.get_value(d.payment_document, d.payment_entry, "clearance_date")

				if not d.clearance_date and not d.confirm_unset and prev_clearance_date:
					frappe.throw(_("Row #{0}: Clearance Date is empty. Please check 'Confirm Unset Clearance Date' to confirm and unset Clearance Date for {1}")
						.format(d.idx, d.payment_entry))

				if (None if not d.clearance_date else getdate(d.clearance_date)) != prev_clearance_date:
					frappe.db.set_value(d.payment_document, d.payment_entry, "clearance_date", d.clearance_date)
					clearance_date_updated = True

					frappe.get_doc(dict(
						doctype='Version',
						ref_doctype=d.payment_document,
						docname=d.payment_entry,
						data=frappe.as_json(dict(comment_type="Label", comment=_("Set Clearance Date to {0}".format(
							frappe.utils.formatdate(d.clearance_date) if d.clearance_date else "None"))))
					)).insert(ignore_permissions=True)

		if clearance_date_updated:
			self.get_payment_entries()
			msgprint(_("Clearance Date updated"))
		else:
			msgprint(_("Clearance Date not mentioned"))
