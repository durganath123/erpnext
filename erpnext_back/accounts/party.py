# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe, erpnext
from frappe import _, msgprint, scrub
from frappe.core.doctype.user_permission.user_permission import get_permitted_documents
from frappe.model.utils import get_fetch_values
from frappe.utils import (add_days, getdate, formatdate, date_diff,
	add_years, get_timestamp, nowdate, flt, cstr, cint, add_months, get_last_day)
from frappe.contacts.doctype.address.address import (get_address_display,
	get_default_address, get_company_address)
from frappe.contacts.doctype.contact.contact import get_contact_details, get_default_contact
from erpnext.exceptions import PartyFrozen, PartyDisabled, InvalidAccountCurrency
from erpnext.accounts.utils import get_fiscal_year
from erpnext import get_company_currency
import json

from six import iteritems, string_types

class DuplicatePartyAccountError(frappe.ValidationError): pass

@frappe.whitelist()
def get_party_details(party=None, account=None, party_type="Customer", company=None, posting_date=None, letter_of_credit=None,
	bill_date=None, price_list=None, currency=None, doctype=None, ignore_permissions=False, fetch_payment_terms_template=True,
	party_address=None, company_address=None, shipping_address=None, pos_profile=None):

	if not party:
		return {}
	if not frappe.db.exists(party_type, party):
		frappe.throw(_("{0}: {1} does not exists").format(party_type, party))
	return _get_party_details(party, account, party_type, letter_of_credit,
		company, posting_date, bill_date, price_list, currency, doctype, ignore_permissions,
		fetch_payment_terms_template, party_address, company_address, shipping_address, pos_profile)

def _get_party_details(party=None, account=None, party_type="Customer", letter_of_credit=None, company=None, posting_date=None,
	bill_date=None, price_list=None, currency=None, doctype=None, ignore_permissions=False,
	fetch_payment_terms_template=True, party_address=None, company_address=None,shipping_address=None, pos_profile=None):

	party_details = frappe._dict(set_due_date(party, party_type, company, posting_date, bill_date, doctype))
	party = party_details[scrub(party_type)]

	if not ignore_permissions and not frappe.has_permission(party_type, "read", party):
		frappe.throw(_("Not permitted for {0}").format(party), frappe.PermissionError)

	if party or letter_of_credit:
		account = get_party_account("Letter of Credit" if letter_of_credit else party_type,
									letter_of_credit if letter_of_credit else party, company)
		account_fieldname = "debit_to" if party_type=="Customer" else "credit_to"
		party_details[account_fieldname] = account

	party = frappe.get_doc(party_type, party)
	currency = party.default_currency if party.get("default_currency") else get_company_currency(company)

	party_address, shipping_address = set_address_details(party_details, party, party_type, doctype, company, party_address, company_address, shipping_address)
	set_contact_details(party_details, party, party_type)
	set_other_values(party_details, party, party_type)
	set_price_list(party_details, party, party_type, price_list, pos_profile)

	party_details["tax_category"] = get_address_tax_category(party.get("tax_category"),
		party_address, shipping_address if party_type != "Supplier" else party_address)

	if not party_details.get("taxes_and_charges"):
		party_details["taxes_and_charges"] = set_taxes(party.name, party_type, posting_date, company,
			customer_group=party_details.customer_group, supplier_group=party_details.supplier_group, tax_category=party_details.tax_category,
			billing_address=party_address, shipping_address=shipping_address)

	if fetch_payment_terms_template:
		party_details["payment_terms_template"] = get_pyt_term_template(party.name, party_type, company)

	if not party_details.get("currency"):
		party_details["currency"] = currency

	# sales team
	if party_type=="Customer":
		party_details["sales_team"] = [{
			"sales_person": d.sales_person,
			"allocated_percentage": d.allocated_percentage or None
		} for d in party.get("sales_team")]

	# supplier tax withholding category
	if party_type == "Supplier" and party:
		party_details["supplier_tds"] = frappe.get_value(party_type, party.name, "tax_withholding_category")

	if doctype == "Purchase Invoice" and party_type == "Supplier":
		party_details["on_hold"] = cint(party.get('hold_invoices_by_default'))

	if doctype == "Sales Order":
		from erpnext.selling.doctype.customer.customer import get_credit_limit, get_customer_outstanding
		party_details["customer_credit_limit"] = get_credit_limit(party.name, company)
		party_details["customer_outstanding_amount"] = frappe.db.sql("""
			select ifnull(sum(debit) - sum(credit), 0)
			from `tabGL Entry`
			where party_type = 'Customer' and party = %s and company=%s""", (party.name, company))
		party_details["customer_outstanding_amount"] = party_details["customer_outstanding_amount"][0][0] if party_details["customer_outstanding_amount"] else 0

	if party.get('party_warehouse'):
		party_details['set_warehouse'] = party.get('party_warehouse')

	return party_details

def set_address_details(party_details, party, party_type, doctype=None, company=None, party_address=None, company_address=None, shipping_address=None):
	billing_address_field = "customer_address" if party_type == "Lead" \
		else scrub(party_type) + "_address"
	party_details[billing_address_field] = party_address or get_default_address(party_type, party.name)
	if doctype:
		party_details.update(get_fetch_values(doctype, billing_address_field, party_details[billing_address_field]))
	# address display
	party_details.address_display = get_address_display(party_details[billing_address_field])
	# shipping address
	if party_type in ["Customer", "Lead", "Supplier"]:
		party_details.shipping_address_name = shipping_address or get_party_shipping_address(party_type, party.name)
		party_details.shipping_address = get_address_display(party_details["shipping_address_name"])
		if doctype:
			party_details.update(get_fetch_values(doctype, 'shipping_address_name', party_details.shipping_address_name))

	if company_address:
		party_details.update({'company_address': company_address})
	else:
		party_details.update(get_company_address(company))

	return party_details.get(billing_address_field), party_details.shipping_address_name

@erpnext.allow_regional
def get_regional_address_details(party_details, doctype, company):
	pass

def set_contact_details(party_details, party, party_type):
	party_details.contact_person = get_default_contact(party_type, party.name)

	if not party_details.contact_person:
		party_details.update({
			"contact_person": None,
			"contact_display": None,
			"contact_email": None,
			"contact_mobile": None,
			"contact_phone": None,
			"contact_designation": None,
			"contact_department": None
		})
	else:
		party_details.update(get_contact_details(party_details.contact_person))

def set_other_values(party_details, party, party_type):
	# copy
	if party_type=="Customer":
		to_copy = ["customer_name", "customer_group", "territory", "language", "default_sales_partner", "default_commission_rate"]
	else:
		to_copy = ["supplier_name", "supplier_group", "language"]
	for f in to_copy:
		party_details[f] = party.get(f)

def get_default_price_list(party):
	"""Return default price list for party (Document object)"""
	if party.get("default_price_list"):
		return party.default_price_list

	if party.doctype == "Customer":
		price_list =  frappe.get_cached_value("Customer Group",
			party.customer_group, "default_price_list")
		if price_list:
			return price_list

	return None

def set_price_list(party_details, party, party_type, given_price_list, pos=None):
	# price list
	price_list = get_permitted_documents('Price List')

	# if there is only one permitted document based on user permissions, set it
	if price_list and len(price_list) == 1:
		price_list = price_list[0]
	elif pos and party_type == 'Customer':
		customer_price_list = frappe.get_value('Customer', party.name, 'default_price_list')

		if customer_price_list:
			price_list = customer_price_list
		else:
			pos_price_list = frappe.get_value('POS Profile', pos, 'selling_price_list')
			price_list = pos_price_list or given_price_list
	else:
		price_list = get_default_price_list(party) or given_price_list

	if price_list:
		party_details.price_list_currency = frappe.db.get_value("Price List", price_list, "currency", cache=True)

	party_details["selling_price_list" if party.doctype=="Customer" else "buying_price_list"] = price_list


def set_due_date(party, party_type, company, posting_date, bill_date, doctype):
	if doctype not in ["Sales Invoice", "Purchase Invoice"]:
		# not an invoice
		return {
			scrub(party_type): party
		}

	out = {
		scrub(party_type): party,
		"due_date": get_due_date(posting_date, party_type, party, company, bill_date)
	}

	return out

@frappe.whitelist()
def get_party_account(party_type, party, company):
	"""Returns the account for the given `party`.
		Will first search in party (Customer / Supplier) record, if not found,
		will search in group (Customer Group / Supplier Group),
		finally will return default."""
	if not company:
		frappe.throw(_("Please select a Company"))

	if not party:
		return

	account = frappe.db.get_value("Party Account",
		{"parenttype": party_type, "parent": party, "company": company}, "account")

	if not account and party_type in ['Customer', 'Supplier']:
		party_group_doctype = "Customer Group" if party_type=="Customer" else "Supplier Group"
		group = frappe.get_cached_value(party_type, party, scrub(party_group_doctype))
		account = frappe.db.get_value("Party Account",
			{"parenttype": party_group_doctype, "parent": group, "company": company}, "account")

	if not account and party_type in ['Customer', 'Supplier', 'Letter of Credit']:
		if party_type == "Customer":
			default_account_name = "default_receivable_account"
		elif party_type == "Supplier":
			default_account_name = "default_payable_account"
		else:
			default_account_name = "default_letter_of_credit_account"

		account = frappe.get_cached_value('Company',  company,  default_account_name)

	existing_gle_currency = get_party_gle_currency(party_type, party, company)
	if existing_gle_currency:
		if account:
			account_currency = frappe.db.get_value("Account", account, "account_currency", cache=True)
		if (account and account_currency != existing_gle_currency) or not account:
				account = get_party_gle_account(party_type, party, company)

	return account

@frappe.whitelist()
def get_party_bank_account(party_type, party):
	return frappe.db.get_value('Bank Account', {
		'party_type': party_type,
		'party': party,
		'is_default': 1
	})

def get_party_account_currency(party_type, party, company):
	def generator():
		party_account = get_party_account(party_type, party, company)
		return frappe.db.get_value("Account", party_account, "account_currency", cache=True)

	return frappe.local_cache("party_account_currency", (party_type, party, company), generator)

def get_party_gle_currency(party_type, party, company):
	def generator():
		existing_gle_currency = frappe.db.sql("""select account_currency from `tabGL Entry`
			where docstatus=1 and company=%(company)s and party_type=%(party_type)s and party=%(party)s
			limit 1""", { "company": company, "party_type": party_type, "party": party })

		return existing_gle_currency[0][0] if existing_gle_currency else None

	return frappe.local_cache("party_gle_currency", (party_type, party, company), generator,
		regenerate_if_none=True)

def get_party_gle_account(party_type, party, company):
	def generator():
		existing_gle_account = frappe.db.sql("""select account from `tabGL Entry`
			where docstatus=1 and company=%(company)s and party_type=%(party_type)s and party=%(party)s
			limit 1""", { "company": company, "party_type": party_type, "party": party })

		return existing_gle_account[0][0] if existing_gle_account else None

	return frappe.local_cache("party_gle_account", (party_type, party, company), generator,
		regenerate_if_none=True)

def validate_party_gle_currency(party_type, party, company, party_account_currency=None):
	"""Validate party account currency with existing GL Entry's currency"""
	if not party_account_currency:
		party_account_currency = get_party_account_currency(party_type, party, company)

	existing_gle_currency = get_party_gle_currency(party_type, party, company)

	if existing_gle_currency and party_account_currency != existing_gle_currency:
		frappe.throw(_("Accounting Entry for {0}: {1} can only be made in currency: {2}")
			.format(party_type, party, existing_gle_currency), InvalidAccountCurrency)

def validate_party_accounts(doc):
	companies = []

	for account in doc.get("accounts"):
		if account.company in companies:
			frappe.throw(_("There can only be 1 Account per Company in {0} {1}")
				.format(doc.doctype, doc.name), DuplicatePartyAccountError)
		else:
			companies.append(account.company)

		party_account_currency = frappe.db.get_value("Account", account.account, "account_currency", cache=True)
		existing_gle_currency = get_party_gle_currency(doc.doctype, doc.name, account.company)
		if frappe.db.get_default("Company"):
			company_default_currency = frappe.get_cached_value('Company',
				frappe.db.get_default("Company"),  "default_currency")
		else:
			company_default_currency = frappe.db.get_value('Company', account.company, "default_currency")

		if existing_gle_currency and party_account_currency != existing_gle_currency:
			frappe.throw(_("Accounting entries have already been made in currency {0} for company {1}. Please select a receivable or payable account with currency {0}.").format(existing_gle_currency, account.company))

		if doc.get("default_currency") and party_account_currency and company_default_currency:
			if doc.default_currency != party_account_currency and doc.default_currency != company_default_currency:
				frappe.throw(_("Billing currency must be equal to either default company's currency or party account currency"))


@frappe.whitelist()
def get_due_date(posting_date, party_type, party, company=None, bill_date=None):
	"""Get due date from `Payment Terms Template`"""
	due_date = None
	if (bill_date or posting_date) and party:
		due_date = bill_date or posting_date
		template_name = get_pyt_term_template(party, party_type, company)

		if template_name:
			due_date = get_due_date_from_template(template_name, posting_date, bill_date).strftime("%Y-%m-%d")
		else:
			if party_type == "Supplier":
				supplier_group = frappe.get_cached_value(party_type, party, "supplier_group")
				template_name = frappe.get_cached_value("Supplier Group", supplier_group, "payment_terms")
				if template_name:
					due_date = get_due_date_from_template(template_name, posting_date, bill_date).strftime("%Y-%m-%d")
	# If due date is calculated from bill_date, check this condition
	if getdate(due_date) < getdate(posting_date):
		due_date = posting_date
	return due_date

def get_due_date_from_template(template_name, posting_date, bill_date):
	"""
	Inspects all `Payment Term`s from the a `Payment Terms Template` and returns the due
	date after considering all the `Payment Term`s requirements.
	:param template_name: Name of the `Payment Terms Template`
	:return: String representing the calculated due date
	"""
	due_date = getdate(bill_date or posting_date)

	template = frappe.get_doc('Payment Terms Template', template_name)

	for term in template.terms:
		if term.due_date_based_on == 'Day(s) after invoice date':
			due_date = max(due_date, add_days(due_date, term.credit_days))
		elif term.due_date_based_on == 'Day(s) after the end of the invoice month':
			due_date = max(due_date, add_days(get_last_day(due_date), term.credit_days))
		else:
			due_date = max(due_date, add_months(get_last_day(due_date), term.credit_months))
	return due_date

def validate_due_date(posting_date, due_date, party_type, party, company=None, bill_date=None, template_name=None):
	if getdate(due_date) < getdate(posting_date):
		frappe.throw(_("Due Date cannot be before Posting / Supplier Invoice Date"))
	else:
		if not template_name: return

		default_due_date = get_due_date_from_template(template_name, posting_date, bill_date).strftime("%Y-%m-%d")

		if not default_due_date:
			return

		if default_due_date != posting_date and getdate(due_date) > getdate(default_due_date):
			is_credit_controller = frappe.db.get_single_value("Accounts Settings", "credit_controller") in frappe.get_roles()
			if is_credit_controller:
				msgprint(_("Note: Due / Reference Date exceeds allowed customer credit days by {0} day(s)")
					.format(date_diff(due_date, default_due_date)))
			else:
				frappe.throw(_("Due / Reference Date cannot be after {0}")
					.format(formatdate(default_due_date)))

@frappe.whitelist()
def get_address_tax_category(tax_category=None, billing_address=None, shipping_address=None):
	addr_tax_category_from = frappe.db.get_single_value("Accounts Settings", "determine_address_tax_category_from")
	if addr_tax_category_from == "Shipping Address":
		if shipping_address:
			tax_category = frappe.db.get_value("Address", shipping_address, "tax_category") or tax_category
	else:
		if billing_address:
			tax_category = frappe.db.get_value("Address", billing_address, "tax_category") or tax_category

	return cstr(tax_category)

@frappe.whitelist()
def set_taxes(party, party_type, posting_date, company, customer_group=None, supplier_group=None, tax_category=None,
	billing_address=None, shipping_address=None, use_for_shopping_cart=None):
	from erpnext.accounts.doctype.tax_rule.tax_rule import get_tax_template, get_party_details
	args = {
		scrub(party_type): party,
		"company":			company
	}

	if tax_category:
		args['tax_category'] = tax_category

	if customer_group:
		args['customer_group'] = customer_group

	if supplier_group:
		args['supplier_group'] = supplier_group

	if billing_address or shipping_address:
		args.update(get_party_details(party, party_type, {"billing_address": billing_address, \
			"shipping_address": shipping_address }))
	else:
		args.update(get_party_details(party, party_type))

	if party_type in ("Customer", "Lead"):
		args.update({"tax_type": "Sales"})

		if party_type=='Lead':
			args['customer'] = None
			del args['lead']
	else:
		args.update({"tax_type": "Purchase"})

	if use_for_shopping_cart:
		args.update({"use_for_shopping_cart": use_for_shopping_cart})

	return get_tax_template(posting_date, args)


@frappe.whitelist()
def get_pyt_term_template(party_name, party_type, company=None):
	if party_type not in ("Customer", "Supplier"):
		return
	template = None
	if party_type == 'Customer':
		customer = frappe.get_cached_value("Customer", party_name,
			fieldname=['payment_terms', "customer_group"], as_dict=1)
		template = customer.payment_terms

		if not template and customer.customer_group:
			template = frappe.get_cached_value("Customer Group",
				customer.customer_group, 'payment_terms')
	else:
		supplier = frappe.get_cached_value("Supplier", party_name,
			fieldname=['payment_terms', "supplier_group"], as_dict=1)
		template = supplier.payment_terms
		if not template and supplier.supplier_group:
			template = frappe.get_cached_value("Supplier Group", supplier.supplier_group, 'payment_terms')

	if not template and company:
		template = frappe.get_cached_value('Company',  company,  fieldname='payment_terms')
	return template

def validate_party_frozen_disabled(party_type, party_name):
	if frappe.flags.ignored_closed_or_disabled:
		return

	if party_type and party_name:
		if party_type in ("Customer", "Supplier", "Letter of Credit"):
			party = frappe.get_cached_value(party_type, party_name, ["is_frozen", "disabled"], as_dict=True)
			if party.disabled:
				frappe.throw(_("{0} {1} is disabled").format(party_type, party_name), PartyDisabled)
			elif party.get("is_frozen"):
				frozen_accounts_modifier = frappe.db.get_single_value( 'Accounts Settings', 'frozen_accounts_modifier')
				if not frozen_accounts_modifier in frappe.get_roles():
					frappe.throw(_("{0} {1} is frozen").format(party_type, party_name), PartyFrozen)

		elif party_type == "Employee":
			if frappe.db.get_value("Employee", party_name, "status") == "Left":
				frappe.msgprint(_("{0} {1} is not active").format(party_type, party_name), alert=True)

def get_timeline_data(doctype, name):
	'''returns timeline data for the past one year'''
	from frappe.desk.form.load import get_communication_data

	out = {}
	fields = 'creation, count(*)'
	after = add_years(None, -1).strftime('%Y-%m-%d')
	group_by='group by Date(creation)'

	data = get_communication_data(doctype, name, after=after, group_by='group by creation',
		fields='C.creation as creation, count(C.name)',as_dict=False)

	# fetch and append data from Activity Log
	data += frappe.db.sql("""select {fields}
		from `tabActivity Log`
		where (reference_doctype=%(doctype)s and reference_name=%(name)s)
		or (timeline_doctype in (%(doctype)s) and timeline_name=%(name)s)
		or (reference_doctype in ("Quotation", "Opportunity") and timeline_name=%(name)s)
		and status!='Success' and creation > {after}
		{group_by} order by creation desc
		""".format(fields=fields, group_by=group_by, after=after), {
			"doctype": doctype,
			"name": name
		}, as_dict=False)

	timeline_items = dict(data)

	for date, count in iteritems(timeline_items):
		timestamp = get_timestamp(date)
		out.update({ timestamp: count })

	return out

def get_dashboard_info(party_type, party, loyalty_program=None):
	current_fiscal_year = get_fiscal_year(nowdate(), as_dict=True)

	doctype = "Sales Invoice" if party_type=="Customer" else "Purchase Invoice"

	companies = frappe.get_all(doctype, filters={
		'docstatus': 1,
		scrub(party_type): party
	}, distinct=1, fields=['company'])
	companies = companies or [frappe._dict({"company": erpnext.get_default_company()})]

	company_wise_info = []

	company_wise_grand_total = frappe.db.sql("""
		select company, sum(debit_in_account_currency) - sum(credit_in_account_currency) as grand_total,
			sum(debit) - sum(credit) as base_grand_total
		from `tabGL Entry`
		where party_type = %s and party=%s and voucher_type = '{0}' and ifnull(against_voucher, '') = ''
			and posting_date between %s and %s
		group by company
	""".format(doctype), [party_type, party, current_fiscal_year.year_start_date, current_fiscal_year.year_end_date], as_dict=1)

	loyalty_point_details = []

	if party_type == "Customer":
		loyalty_point_details = frappe._dict(frappe.get_all("Loyalty Point Entry",
			filters={
				'customer': party,
				'expiry_date': ('>=', getdate()),
				},
				group_by="company",
				fields=["company", "sum(loyalty_points) as loyalty_points"],
				as_list =1
			))

	company_wise_billing_this_year = frappe._dict()

	for d in company_wise_grand_total:
		company_wise_billing_this_year.setdefault(
			d.company,{
				"grand_total": d.grand_total,
				"base_grand_total": d.base_grand_total
			})

	company_wise_total_unpaid = frappe._dict(frappe.db.sql("""
		select company, sum(debit_in_account_currency) - sum(credit_in_account_currency)
		from `tabGL Entry`
		where party_type = %s and party=%s
		group by company""", (party_type, party)))

	for d in companies:
		company_default_currency = frappe.db.get_value("Company", d.company, 'default_currency')
		party_account_currency = get_party_account_currency(party_type, party, d.company)

		if party_account_currency==company_default_currency:
			billing_this_year = flt(company_wise_billing_this_year.get(d.company,{}).get("base_grand_total"))
		else:
			billing_this_year = flt(company_wise_billing_this_year.get(d.company,{}).get("grand_total"))

		total_unpaid = flt(company_wise_total_unpaid.get(d.company))

		if loyalty_point_details:
			loyalty_points = loyalty_point_details.get(d.company)

		info = {}
		info["billing_this_year"] = flt(billing_this_year) if billing_this_year else 0
		info["currency"] = party_account_currency
		info["total_unpaid"] = flt(total_unpaid) if total_unpaid else 0
		info["company"] = d.company

		if party_type == "Customer" and loyalty_point_details:
			info["loyalty_points"] = loyalty_points

		if party_type == "Supplier":
			info["billing_this_year"] = -1 * info["billing_this_year"]
			info["total_unpaid"] = -1 * info["total_unpaid"]

		company_wise_info.append(info)

	return company_wise_info

def get_party_shipping_address(doctype, name):
	"""
	Returns an Address name (best guess) for the given doctype and name for which `address_type == 'Shipping'` is true.
	and/or `is_shipping_address = 1`.

	It returns an empty string if there is no matching record.

	:param doctype: Party Doctype
	:param name: Party name
	:return: String
	"""
	out = frappe.db.sql(
		'SELECT dl.parent '
		'from `tabDynamic Link` dl join `tabAddress` ta on dl.parent=ta.name '
		'where '
		'dl.link_doctype=%s '
		'and dl.link_name=%s '
		'and dl.parenttype="Address" '
		'and ifnull(ta.disabled, 0) = 0 and'
		'(ta.address_type in ("Shipping", "Warehouse") or ta.is_shipping_address=1) '
		'order by ta.is_shipping_address desc, ta.address_type desc limit 1',
		(doctype, name)
	)
	if out:
		return out[0][0]
	else:
		return ''

def get_partywise_advanced_payment_amount(party_type, posting_date = None, future_payment=0, company=None):
	cond = "1=1"
	if posting_date:
		if future_payment:
			cond = "posting_date <= '{0}' OR DATE(creation) <= '{0}' """.format(posting_date)
		else:
			cond = "posting_date <= '{0}'".format(posting_date)

	if company:
		cond += "and company = '{0}'".format(company)

	data = frappe.db.sql(""" SELECT party, sum({0}) as amount
		FROM `tabGL Entry`
		WHERE
			party_type = %s and (ifnull(against_voucher, '') = '' or against_voucher_type in ('Sales Order', 'Purchase Order'))
			and {1} GROUP BY party"""
		.format(("credit") if party_type == "Customer" else "debit", cond) , party_type)

	if data:
		return frappe._dict(data)


@frappe.whitelist()
def get_party_default_items(args, existing_item_codes=None, with_valuation_rates=False):
	from erpnext.stock.get_item_details import get_item_details
	from erpnext.accounts.report.gross_profit.gross_profit import update_item_batch_incoming_rate
	from collections import OrderedDict

	if not existing_item_codes:
		existing_item_codes = []
	if isinstance(args, string_types):
		args = json.loads(args)
	if isinstance(existing_item_codes, string_types):
		existing_item_codes = json.loads(existing_item_codes)

	if not args.get('customer') and not args.get('supplier'):
		return []

	if args.get('customer'):
		party_type = 'Customer'
		party = args.get('customer')
	else:
		party_type = 'Supplier'
		party = args.get('supplier')

	default_items = frappe.get_all("Customer Default Item", fields=['item_code'],
		filters={"parenttype": party_type, "parent": party})
	item_codes = [d.item_code for d in default_items
		if d.item_code not in existing_item_codes and not cint(frappe.get_cached_value("Item", d.item_code, "disabled"))]

	item_group_wise_data = OrderedDict()
	for item_code in item_codes:
		item_args = args.copy()
		item_args['item_code'] = item_code

		item_details = get_item_details(item_args, skip_valuation_rates=True)
		item_group_wise_data.setdefault(item_details.get('item_group'), []).append(item_details)

	out = []
	stock_settings = frappe.get_cached_doc("Stock Settings", None)

	for item_group in stock_settings.price_list_order or []:
		if item_group.item_group in item_group_wise_data:
			out += sorted(item_group_wise_data[item_group.item_group], key=lambda d: d.item_code)
			del item_group_wise_data[item_group.item_group]

	for items in item_group_wise_data.values():
		out += sorted(items, key=lambda d: d.item_code)

	if with_valuation_rates:
		update_item_batch_incoming_rate(out, doc=args)

	return reversed(out)


@frappe.whitelist()
def add_item_codes_to_party_default_items(party_type, party, item_codes):
	if isinstance(item_codes, string_types):
		item_codes = json.loads(item_codes)

	doc = frappe.get_doc(party_type, party)

	existing_item_codes = list(map(lambda d: d.item_code, doc.default_items_tbl))
	item_codes = list(filter(lambda item_code: item_code not in existing_item_codes, item_codes))

	if not item_codes:
		frappe.msgprint(_("Selected items already exists in {0} Default Items").format(party_type))
		return

	for item_code in item_codes:
		doc.append("default_items_tbl", {
			"item_code": item_code,
			"item_name": frappe.get_cached_value("Item", item_code, "item_name")
		})

	doc.save()

	frappe.msgprint(_("Selected items added to {0} Default Items").format(party_type))


@frappe.whitelist()
def remove_item_codes_from_party_default_items(party_type, party, item_codes):
	if isinstance(item_codes, string_types):
		item_codes = json.loads(item_codes)

	doc = frappe.get_doc(party_type, party)
	doc.default_items_tbl = list(filter(lambda d: d.item_code not in item_codes, doc.default_items_tbl))
	for i, d in enumerate(doc.default_items_tbl):
		d.idx = i + 1

	doc.save()

	frappe.msgprint(_("Selected items removed from {0} Default Items").format(party_type))