# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt, getdate, nowdate
from frappe import _
from erpnext.accounts.utils import get_balance_on

def execute(filters=None):
	columns = get_columns()

	if not filters:
		filters = {}
	if not filters.get("account"):
		return columns, []

	filters["report_date"] = getdate(filters["report_date"])
	filters["from_date"] = getdate(filters["from_date"])

	account_currency = frappe.db.get_value("Account", filters.account, "account_currency")
	closing_balance_as_per_system = get_balance_on(filters["account"], filters["report_date"])
	opening_balance_as_per_statement = get_bank_statement_balance(filters)

	entries = get_entries(filters)

	uncleared_incoming = []
	uncleared_outgoing = []
	cleared_incoming = []
	cleared_outgoing = []
	total_uncleared_incoming, total_uncleared_outgoing, total_cleared_incoming, total_cleared_outgoing = 0, 0, 0, 0

	for d in entries:
		d.indent = 1

		is_cleared = d.get('clearance_date')\
			and filters['from_date'] <= getdate(d.get('clearance_date')) <= filters['report_date']
		diff = d.debit - d.credit

		if diff > 0:
			if is_cleared:
				cleared_incoming.append(d)
				total_cleared_incoming += diff
			else:
				uncleared_incoming.append(d)
				total_uncleared_incoming += diff
		else:
			if is_cleared:
				cleared_outgoing.append(d)
				total_cleared_outgoing += diff
			else:
				uncleared_outgoing.append(d)
				total_uncleared_outgoing += diff

	closing_balance_as_per_statement = flt(opening_balance_as_per_statement) + flt(total_cleared_incoming) \
		+ flt(total_cleared_outgoing)

	# noinspection PyListCreation
	data = [
		get_balance_row(_("'Calculated Opening Opening Bank Statement Balance'"), opening_balance_as_per_statement, account_currency),
		{}
	]

	data.append(get_balance_row(_("'Total Uncleared Incoming'"), total_uncleared_incoming, account_currency))
	data += uncleared_incoming
	data.append({})
	data.append(get_balance_row(_("'Total Uncleared Outgoing'"), total_uncleared_outgoing, account_currency))
	data += uncleared_outgoing
	data.append({})
	data.append(get_balance_row(_("'Total Cleared Incoming'"), total_cleared_incoming, account_currency, collapsed=True))
	data += cleared_incoming
	data.append({})
	data.append(get_balance_row(_("'Total Cleared Outgoing'"), total_cleared_outgoing, account_currency, collapsed=True))
	data += cleared_outgoing
	data.append({})

	data += [
		get_balance_row(_("'Closing Bank Balance as per General Ledger'"), closing_balance_as_per_system, account_currency),\
		get_balance_row(_("'Calculated Closing Bank Statement Balance'"), closing_balance_as_per_statement, account_currency)
	]

	return columns, data


def get_entries(filters):
	journal_entries = frappe.db.sql("""
		select "Journal Entry" as payment_document, jv.posting_date, 
			jv.name as payment_entry, jvd.debit_in_account_currency as debit, 
			jvd.credit_in_account_currency as credit, jvd.against_account, 
			jv.cheque_no as reference_no, jv.cheque_date as ref_date, jv.clearance_date, jvd.account_currency
		from
			`tabJournal Entry Account` jvd, `tabJournal Entry` jv
		where jvd.parent = jv.name and jv.docstatus=1
			and jvd.account = %(account)s
			and (jv.posting_date between %(from_date)s and %(report_date)s or jv.clearance_date between %(from_date)s and %(report_date)s)
			and jv.is_opening != 'Yes'""", filters, as_dict=1)
			
	payment_entries = frappe.db.sql("""
		select 
			"Payment Entry" as payment_document, name as payment_entry, 
			reference_no, reference_date as ref_date, 
			if(paid_to=%(account)s, received_amount, 0) as debit, 
			if(paid_from=%(account)s, paid_amount, 0) as credit, 
			posting_date, ifnull(party,if(paid_from=%(account)s,paid_to,paid_from)) as against_account, clearance_date,
			if(paid_to=%(account)s, paid_to_account_currency, paid_from_account_currency) as account_currency
		from `tabPayment Entry`
		where
			(paid_from=%(account)s or paid_to=%(account)s) and docstatus=1
			and (posting_date between %(from_date)s and %(report_date)s or clearance_date between %(from_date)s and %(report_date)s)
	""", filters, as_dict=1)

	pos_entries = []
	if filters.include_pos_transactions:
		pos_entries = frappe.db.sql("""
			select
				"Sales Invoice Payment" as payment_document, sip.name as payment_entry, sip.amount as debit,
				si.posting_date, si.debit_to as against_account, sip.clearance_date,
				account.account_currency, 0 as credit
			from `tabSales Invoice Payment` sip, `tabSales Invoice` si, `tabAccount` account
			where
				sip.account=%(account)s and si.docstatus=1 and sip.parent = si.name
				and account.name = sip.account
				and (si.posting_date between %(start_date)s and %(report_date)s or sip.clearance_date between %(start_date)s and %(report_date)s)
		""", filters, as_dict=1)

	return sorted(payment_entries + journal_entries + pos_entries, key=lambda k: k['posting_date'] or getdate(nowdate()))


def get_bank_statement_balance(filters):
	je_amount = frappe.db.sql("""
		select sum(jvd.debit_in_account_currency - jvd.credit_in_account_currency)
		from `tabJournal Entry Account` jvd, `tabJournal Entry` jv
		where jvd.parent = jv.name and jv.docstatus=1 and jvd.account=%(account)s and (
			jv.is_opening = 'Yes'
			or (jv.clearance_date < %(from_date)s and jv.clearance_date is not null and jv.clearance_date != '0000-00-00')
		)
	""", filters)

	je_amount = flt(je_amount[0][0]) if je_amount else 0.0

	pe_amount = frappe.db.sql("""
		select sum(if(paid_from=%(account)s, -paid_amount, received_amount))
		from `tabPayment Entry`
		where (paid_from=%(account)s or paid_to=%(account)s) and docstatus=1
			and clearance_date < %(from_date)s and clearance_date is not null and clearance_date != '0000-00-00'
	""", filters)

	pe_amount = flt(pe_amount[0][0]) if pe_amount else 0.0

	pos_amount = frappe.db.sql("""
		select sum(sip.amount)
		from `tabSales Invoice Payment` sip, `tabSales Invoice` si
		where sip.account=%(account)s and si.docstatus=1 and sip.parent = si.name
			and clearance_date < %(from_date)s and clearance_date is not null and clearance_date != '0000-00-00'
	""", filters)

	pos_amount = flt(pos_amount[0][0]) if pos_amount else 0.0

	return je_amount + pe_amount + pos_amount


def get_balance_row(label, amount, account_currency, collapsed=False):
	if amount > 0:
		return {
			"payment_entry": label,
			"debit": amount,
			"credit": 0,
			"account_currency": account_currency,
			"_bold": 1,
			"_collapsed": collapsed
		}
	else:
		return {
			"payment_entry": label,
			"debit": 0,
			"credit": abs(amount),
			"account_currency": account_currency,
			"_bold": 1,
			"_collapsed": collapsed
		}


def get_columns():
	return [
		{
			"fieldname": "payment_entry",
			"label": _("Payment Entry"),
			"fieldtype": "Dynamic Link",
			"options": "payment_document",
			"width": 250
		},
		{
			"fieldname": "posting_date",
			"label": _("Posting Date"),
			"fieldtype": "Date",
			"width": 90
		},
		{
			"fieldname": "clearance_date",
			"label": _("Clearance Date"),
			"fieldtype": "Date",
			"width": 110
		},
		{
			"fieldname": "reference_no",
			"label": _("Reference"),
			"fieldtype": "Data",
			"width": 100
		},
		{
			"fieldname": "debit",
			"label": _("Debit"),
			"fieldtype": "Currency",
			"options": "account_currency",
			"width": 120
		},
		{
			"fieldname": "credit",
			"label": _("Credit"),
			"fieldtype": "Currency",
			"options": "account_currency",
			"width": 120
		},
		{
			"fieldname": "against_account",
			"label": _("Against Account"),
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "account_currency",
			"label": _("Currency"),
			"fieldtype": "Link",
			"options": "Currency",
			"width": 100
		}
	]