# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import throw, _
import frappe.defaults
from frappe.utils import cint, flt, get_fullname, cstr, today
from frappe.contacts.doctype.address.address import get_address_display
from erpnext.shopping_cart.doctype.shopping_cart_settings.shopping_cart_settings import get_shopping_cart_settings
from frappe.utils.nestedset import get_root_of
from erpnext.accounts.utils import get_account_name
from erpnext.utilities.product import get_qty_in_stock
from erpnext.accounts.utils import get_balance_on


class WebsitePriceListMissingError(frappe.ValidationError):
	pass

cart_quotation_fields = ['delivery_date', 'contact_display']
cart_party_fields = ['customer_name', 'credit_limit']

def set_cart_count(quotation=None):
	if cint(frappe.db.get_singles_value("Shopping Cart Settings", "enabled")):
		if not quotation:
			quotation = _get_cart_quotation()
		cart_count = cstr(len(quotation.get("items")))

		if hasattr(frappe.local, "cookie_manager"):
			frappe.local.cookie_manager.set_cookie("cart_count", cart_count)


def get_cart_quotation(doc=None, name=None):
	party = get_party()

	if not doc:
		quotation = _get_cart_quotation(party, name)
		doc = quotation
		if not doc.confirmed_by_customer:
			set_cart_count(quotation)

	if hasattr(doc, "set_indicator"):
		doc.set_indicator()

	addresses = get_address_docs(party=party)
	get_balance = get_balance_on(party=party.name, party_type='Customer')

	if not doc.customer_address and addresses:
		update_cart_address("customer_address", addresses[0].name)

	doc.get_cart_messages()

	return {
		"title": _("Order Cart"),
		"doc": decorate_quotation_doc(doc),
		"party": party,
		"quotation_fields": cart_quotation_fields,
		"party_fields": cart_party_fields,
		"customer_balance": get_balance,
		"shipping_addresses": [{"name": address.name, "display": address.display} for address in addresses],
		"billing_addresses": [{"name": address.name, "display": address.display} for address in addresses],
		"shipping_rules": get_applicable_shipping_rules(party),
		"default_item_groups_allow": default_item_groups_allow()
	}

@frappe.whitelist()
def place_order(confirmed, with_items=True, name=None):
	def failed(doc):
		context = {'doc': doc}
		frappe.msgprint(_('Could not place order. See errors'), indicator='red')
		return {
			'failed': 1,
			'warnings': frappe.render_template("templates/includes/cart/cart_warnings.html", context),
			'errors': frappe.render_template("templates/includes/cart/cart_errors.html", context)
		}

	confirmed = cint(confirmed)

	quotation = _get_cart_quotation(name=name)
	quotation.company = frappe.db.get_value("Shopping Cart Settings", None, "company")
	quotation.confirmed_by_customer = 1 if confirmed else 0

	if confirmed:
		quotation.remove_zero_qty_items()

		quotation.get_cart_errors()
		if quotation.cart_errors:
			return failed(quotation)

	out = update_cart(quotation, with_items=with_items, ignore_mandatory=False)

	if confirmed:
		if quotation.cart_errors:
			frappe.db.rollback()
			return failed(quotation)

		if quotation.lead:
			# company used to create customer accounts
			frappe.defaults.set_user_default("company", quotation.company)

		if hasattr(frappe.local, "cookie_manager"):
			frappe.local.cookie_manager.delete_cookie("cart_count")

	if confirmed:
		frappe.msgprint(_("Order {0} Sent").format(quotation.name))
	else:
		frappe.msgprint(_("Order {0} Cancelled").format(quotation.name))

	return out

@frappe.whitelist()
def update_cart_item(item_code, fieldname, value, with_items=False, name=None):
	from erpnext.stock.get_item_details import get_conversion_factor

	quotation = _get_cart_quotation(name=name)

	if fieldname not in ['qty', 'uom']:
		frappe.throw(_("Invalid Fieldname"))

	if fieldname == 'qty' and not flt(value):
		quotation_items = quotation.get("items", {"item_code": ["!=", item_code]})
		for i, d in enumerate(quotation_items):
			d.idx = i + 1
		quotation.set("items", quotation_items)
	else:
		quotation_items = quotation.get("items", {"item_code": item_code})
		if not quotation_items:
			quotation.append("items", {
				"item_code": item_code,
				fieldname: value
			})
		else:
			quotation_items[0].set(fieldname, value)
			if fieldname == 'uom':
				quotation_items[0].conversion_factor = get_conversion_factor(item_code, value).get('conversion_factor')

	return update_cart(quotation, with_items)
	

@frappe.whitelist()
def update_cart_field(fieldname, value, with_items=False, name=None):
	if fieldname not in cart_quotation_fields:
		frappe.throw(_("Invalid Fieldname {0}").format(fieldname))

	quotation = _get_cart_quotation(name=name)

	quotation.set(fieldname, value)
	return update_cart(quotation, with_items)

def update_cart(quotation, with_items=False, ignore_mandatory=True):
	apply_cart_settings(quotation=quotation)
	quotation.flags.ignore_permissions = True
	quotation.flags.ignore_mandatory = ignore_mandatory
	quotation.payment_schedule = []
	quotation.save()
	if not quotation.confirmed_by_customer:
		set_cart_count(quotation)

	context = get_cart_quotation(quotation)
	qtn_fields_dict = {}
	for f in cart_quotation_fields:
		qtn_fields_dict[f] = context['doc'].get(f)
	for f in cart_party_fields:
		qtn_fields_dict[f] = context['party'].get(f)
	qtn_fields_dict['customer_balance'] = context.get('customer_balance')

	out = {
		'name': quotation.name,
		'shopping_cart_menu': get_shopping_cart_menu(context),
		'warnings': frappe.render_template("templates/includes/cart/cart_warnings.html", context),
		'errors': frappe.render_template("templates/includes/cart/cart_errors.html", context),
		'indicator': frappe.render_template("templates/includes/cart/cart_indicator.html", context),
		'quotation_fields': qtn_fields_dict
	}
	if cint(with_items):
		out.update({
			"items": frappe.render_template("templates/includes/cart/cart_items.html",
				context) if quotation.delivery_date else "",
			"taxes": frappe.render_template("templates/includes/order/order_taxes.html",
				context) if quotation.delivery_date else "",
			"confirmed_by_customer": quotation.confirmed_by_customer
		})

	return out

@frappe.whitelist()
def get_shopping_cart_menu(context=None):
	if not context:
		context = get_cart_quotation()

	return frappe.render_template('templates/includes/cart/cart_dropdown.html', context)

@frappe.whitelist()
def update_cart_address(address_type, address_name, name=None):
	quotation = _get_cart_quotation(name=name)
	address_display = get_address_display(frappe.get_doc("Address", address_name).as_dict())

	if address_type.lower() == "billing":
		quotation.customer_address = address_name
		quotation.address_display = address_display
		quotation.shipping_address_name == quotation.shipping_address_name or address_name
	elif address_type.lower() == "shipping":
		quotation.shipping_address_name = address_name
		quotation.shipping_address = address_display
		quotation.customer_address == quotation.customer_address or address_name

	apply_cart_settings(quotation=quotation)

	quotation.flags.ignore_permissions = True
	quotation.flags.ignore_mandatory = True
	quotation.save()

	context = get_cart_quotation(quotation)
	return {
		"taxes": frappe.render_template("templates/includes/order/order_taxes.html",
			context),
		"name": quotation.name
		}

def guess_territory():
	territory = None
	geoip_country = frappe.session.get("session_country")
	if geoip_country:
		territory = frappe.db.get_value("Territory", geoip_country)

	return territory or \
		frappe.db.get_value("Shopping Cart Settings", None, "territory") or \
			get_root_of("Territory")

def decorate_quotation_doc(doc):
	for d in doc.get("items", []):
		d.update(frappe.get_cached_value("Item", d.item_code,
			["thumbnail", "website_image", "description", "route", "country_of_origin"], as_dict=True))

		if d.country_of_origin:
			d.country_code = cstr(frappe.get_cached_value("Country", d.country_of_origin, 'code')).upper()

	return doc


def _get_cart_quotation(party=None, name=None):
	'''Return the open Quotation of type "Shopping Cart" or make a new one'''
	if not party:
		party = get_party()

	if not name:
		quotation = frappe.get_all("Quotation", fields=["name"], filters=
			{'quotation_to': party.doctype, 'party_name': party.name, "order_type": "Shopping Cart", "docstatus": 0,
			"confirmed_by_customer": 0},
			order_by="modified desc", limit_page_length=1)

		quotation_name = quotation[0].name if quotation else None
	else:
		quotation_name = name

	qdoc = None
	if quotation_name:
		qdoc = frappe.get_doc("Quotation", quotation_name)
	
	if qdoc:
		if qdoc.docstatus != 0:
			frappe.throw(_("Invalid Order"), frappe.PermissionError)

		if name and not frappe.has_website_permission(qdoc):
			frappe.throw(_("Not Permitted"), frappe.PermissionError)
	else:
		qdoc = frappe.get_doc({
			"doctype": "Quotation",
			"naming_series": get_shopping_cart_settings().quotation_series or "QTN-CART-",
			"quotation_to": party.doctype,
			"company": frappe.db.get_value("Shopping Cart Settings", None, "company"),
			"order_type": "Shopping Cart",
			"status": "Draft",
			"docstatus": 0,
			"__islocal": 1,
			'party_name': party.name
		})

		qdoc.contact_person = frappe.db.get_value("Contact", {"email_id": frappe.session.user})
		qdoc.contact_email = frappe.session.user

		qdoc.flags.ignore_permissions = True
		qdoc.run_method("set_missing_values")
		apply_cart_settings(party, qdoc)

	qdoc.flags.cart_quotation = True
	return qdoc

def update_party(fullname, company_name=None, mobile_no=None, phone=None):
	party = get_party()

	party.customer_name = company_name or fullname
	party.customer_type == "Company" if company_name else "Individual"

	contact_name = frappe.db.get_value("Contact", {"email_id": frappe.session.user})
	contact = frappe.get_doc("Contact", contact_name)
	contact.first_name = fullname
	contact.last_name = None
	contact.customer_name = party.customer_name
	contact.mobile_no = mobile_no
	contact.phone = phone
	contact.flags.ignore_permissions = True
	contact.save()

	party_doc = frappe.get_doc(party.as_dict())
	party_doc.flags.ignore_permissions = True
	party_doc.save()

	qdoc = _get_cart_quotation(party)
	if not qdoc.get("__islocal"):
		qdoc.customer_name = company_name or fullname
		qdoc.run_method("set_missing_lead_customer_details")
		qdoc.flags.ignore_permissions = True
		qdoc.save()

def apply_cart_settings(party=None, quotation=None):
	if not party:
		party = get_party()
	if not quotation:
		quotation = _get_cart_quotation(party)

	quotation.transaction_date = today()

	cart_settings = frappe.get_doc("Shopping Cart Settings")

	set_price_list_and_rate(quotation, cart_settings)

	quotation.run_method("calculate_taxes_and_totals")

	set_taxes(quotation, cart_settings)

	_apply_shipping_rule(party, quotation, cart_settings)

def set_price_list_and_rate(quotation, cart_settings):
	"""set price list based on billing territory"""

	if not quotation.selling_price_list:
		_set_price_list(cart_settings, quotation)

	# reset values
	quotation.price_list_currency = quotation.currency = \
		quotation.plc_conversion_rate = quotation.conversion_rate = None
	for item in quotation.get("items"):
		item.price_list_rate = item.discount_percentage = item.rate = item.amount = None

	# refetch values
	quotation.run_method("set_price_list_and_item_details")

	if hasattr(frappe.local, "cookie_manager"):
		# set it in cookies for using in product page
		frappe.local.cookie_manager.set_cookie("selling_price_list", quotation.selling_price_list)

def _set_price_list(cart_settings, quotation=None):
	"""Set price list based on customer or shopping cart default"""
	from erpnext.accounts.party import get_default_price_list
	party_name = quotation.get("party_name") if quotation else get_party().get("name")
	selling_price_list = None

	# check if default customer price list exists
	if party_name:
		selling_price_list = get_default_price_list(frappe.get_doc("Customer", party_name))

	# check default price list in shopping cart
	if not selling_price_list:
		selling_price_list = cart_settings.price_list

	if quotation:
		quotation.selling_price_list = selling_price_list

	return selling_price_list

def set_taxes(quotation, cart_settings):
	"""set taxes based on billing territory"""
	from erpnext.accounts.party import set_taxes

	customer_group = frappe.db.get_value("Customer", quotation.party_name, "customer_group") if quotation.quotation_to == "Customer" else None

	quotation.taxes_and_charges = set_taxes(quotation.party_name, quotation.quotation_to,
		quotation.transaction_date, quotation.company, customer_group=customer_group, supplier_group=None,
		tax_category=quotation.tax_category, billing_address=quotation.customer_address,
		shipping_address=quotation.shipping_address_name, use_for_shopping_cart=1)
#
# 	# clear table
	quotation.set("taxes", [])
#
# 	# append taxes
	quotation.append_taxes_from_master()

def get_party(user=None, get_contact=False):
	if not user:
		user = frappe.session.user

	contact_name = get_contact_name(user)
	party_doctype = party = None

	if contact_name:
		contact = frappe.get_doc('Contact', contact_name)
		if contact.links:
			party_doctype = contact.links[0].link_doctype
			party = contact.links[0].link_name

	cart_settings = frappe.get_doc("Shopping Cart Settings")

	debtors_account = ''

	if cart_settings.enable_checkout:
		debtors_account = get_debtors_account(cart_settings)

	if party:
		if get_contact:
			return frappe.get_doc(party_doctype, party), contact
		else:
			return frappe.get_doc(party_doctype, party)
	else:
		frappe.throw(_("""You are not allowed to access the Customer Portal because you are not linked to any Customer.
			<a href='/contact' style='font-weight:bold;'>Please contact support</a>."""), frappe.PermissionError)

		if not cart_settings.enabled:
			frappe.local.flags.redirect_location = "/contact"
			raise frappe.Redirect
		customer = frappe.new_doc("Customer")
		fullname = get_fullname(user)
		customer.update({
			"customer_name": fullname,
			"customer_type": "Individual",
			"customer_group": get_shopping_cart_settings().default_customer_group,
			"territory": get_root_of("Territory")
		})

		if debtors_account:
			customer.update({
				"accounts": [{
					"company": cart_settings.company,
					"account": debtors_account
				}]
			})

		customer.flags.ignore_mandatory = True
		customer.insert(ignore_permissions=True)

		contact = frappe.new_doc("Contact")
		contact.update({
			"first_name": fullname,
			"email_id": user,
			"user": user
		})
		contact.append('links', dict(link_doctype='Customer', link_name=customer.name))
		contact.flags.ignore_mandatory = True
		contact.insert(ignore_permissions=True)

		if get_contact:
			return customer, contact
		else:
			return customer

def get_contact_name(user):
	contacts = frappe.db.sql_list("""
		select c.name
		from `tabContact` c
		where (c.user = %(user)s or c.email_id = %(user)s) and exists(select l.name from `tabDynamic Link` l
			where l.parent=c.name and l.parenttype='Contact' and l.link_doctype = 'Customer' and ifnull(l.link_name, '') != '')
	""", {"user": user})

	return contacts[0] if contacts else None

def get_debtors_account(cart_settings):
	payment_gateway_account_currency = \
		frappe.get_doc("Payment Gateway Account", cart_settings.payment_gateway_account).currency

	account_name = _("Debtors ({0})".format(payment_gateway_account_currency))

	debtors_account_name = get_account_name("Receivable", "Asset", is_group=0,\
		account_currency=payment_gateway_account_currency, company=cart_settings.company)

	if not debtors_account_name:
		debtors_account = frappe.get_doc({
			"doctype": "Account",
			"account_type": "Receivable",
			"root_type": "Asset",
			"is_group": 0,
			"parent_account": get_account_name(root_type="Asset", is_group=1, company=cart_settings.company),
			"account_name": account_name,
			"currency": payment_gateway_account_currency
		}).insert(ignore_permissions=True)

		return debtors_account.name

	else:
		return debtors_account_name


def get_address_docs(doctype=None, txt=None, filters=None, limit_start=0, limit_page_length=20,
	party=None):
	if not party:
		party = get_party()

	if not party:
		return []

	address_names = frappe.db.get_all('Dynamic Link', fields=('parent'),
		filters=dict(parenttype='Address', link_doctype=party.doctype, link_name=party.name))

	out = []

	for a in address_names:
		address = frappe.get_doc('Address', a.parent)
		address.display = get_address_display(address.as_dict())
		out.append(address)

	return out

@frappe.whitelist()
def apply_shipping_rule(shipping_rule, name=None):
	quotation = _get_cart_quotation(name=name)

	quotation.shipping_rule = shipping_rule

	apply_cart_settings(quotation=quotation)

	quotation.flags.ignore_permissions = True
	quotation.flags.ignore_mandatory = True
	quotation.save()

	return get_cart_quotation(quotation)

def _apply_shipping_rule(party=None, quotation=None, cart_settings=None):
	if not quotation.shipping_rule:
		shipping_rules = get_shipping_rules(quotation, cart_settings)

		if not shipping_rules:
			return

		elif quotation.shipping_rule not in shipping_rules:
			quotation.shipping_rule = shipping_rules[0]

	if quotation.shipping_rule:
		quotation.run_method("apply_shipping_rule")
		quotation.run_method("calculate_taxes_and_totals")

def get_applicable_shipping_rules(party=None, quotation=None):
	shipping_rules = get_shipping_rules(quotation)

	if shipping_rules:
		rule_label_map = frappe.db.get_values("Shipping Rule", shipping_rules, "label")
		# we need this in sorted order as per the position of the rule in the settings page
		return [[rule, rule_label_map.get(rule)] for rule in shipping_rules]

def get_shipping_rules(quotation=None, cart_settings=None):
	if not quotation:
		quotation = _get_cart_quotation()

	shipping_rules = []
	if quotation.shipping_address_name:
		country = frappe.db.get_value("Address", quotation.shipping_address_name, "country")
		if country:
			shipping_rules = frappe.db.sql_list("""select distinct sr.name
				from `tabShipping Rule Country` src, `tabShipping Rule` sr
				where src.country = %s and
				sr.disabled != 1 and sr.name = src.parent""", country)

	return shipping_rules

def get_address_territory(address_name):
	"""Tries to match city, state and country of address to existing territory"""
	territory = None

	if address_name:
		address_fields = frappe.db.get_value("Address", address_name,
			["city", "state", "country"])
		for value in address_fields:
			territory = frappe.db.get_value("Territory", value)
			if territory:
				break

	return territory

def show_terms(doc):
	return doc.tc_name

@frappe.whitelist()
def get_default_items(with_items=False, item_group=None, name=None):
	quotation = _get_cart_quotation(name=name)

	item_group_join = ""
	if item_group:
		lft_rgt = frappe.get_cached_value("Item Group", item_group, ['lft', 'rgt'])
		if not lft_rgt:
			frappe.throw(_("Invalid Item Group, cannot get default items"), frappe.DoesNotExistError)

		lft, rgt = lft_rgt
		item_group_join = "inner join `tabItem Group` ig on ig.name = i.item_group and ig.lft >= {0} and ig.rgt <= {1}".format(lft, rgt)

	default_item_codes = frappe.db.sql_list("""
		select cdi.item_code
		from `tabCustomer Default Item` cdi
		inner join `tabItem` i on i.name = cdi.item_code {0}
		where i.disabled = 0 and cdi.parenttype = %s and cdi.parent = %s
	""".format(item_group_join), quotation.quotation_to, quotation.party_name)

	existing_item_codes = [d.item_code for d in quotation.items]

	for item_code in default_item_codes:
		if item_code not in existing_item_codes:
			quotation.append("items", {"item_code": item_code, "qty": 0})
	
	return update_cart(quotation, with_items)

def default_item_groups_allow():
	item_groups = frappe.get_all("Item Group", filters={"allow_getting_default_items":1})

	return item_groups

@frappe.whitelist()
def add_item(item_code, with_items=False, name=None):
	quotation = _get_cart_quotation(name=name)
	existing_item_codes = [d.item_code for d in quotation.items]

	if item_code not in existing_item_codes:
		quotation.append("items", {"item_code": item_code, "qty": 1})

	return update_cart(quotation, with_items)


def can_copy_items(doc):
	if doc.doctype == "Quotation":
		return doc.docstatus == 1 or (doc.docstatus == 0 and doc.get('confirmed_by_customer'))
	elif doc.doctype == "Sales Order":
		return doc.docstatus < 2
	else:
		return False


@frappe.whitelist()
def copy_items_from_transaction(dt, dn):
	meta = frappe.get_meta(dt)
	if not meta.has_field('items'):
		frappe.throw(_("Cannot copy items from {0} {1}".format(dt, dn)))

	doc = frappe.get_doc(dt, dn)
	if not frappe.has_website_permission(doc) or not can_copy_items(doc):
		frappe.throw(_("Not Permitted"), frappe.PermissionError)

	quotation = _get_cart_quotation()
	quot_items_list = [d.item_code for d in quotation.items]

	for item in doc.items:
		if item.item_code not in quot_items_list:
			quotation.append("items", {"item_code": item.item_code, "qty": 0})

	return update_cart(quotation)


@frappe.whitelist()
def add_new_address(doc):
	doc = frappe.parse_json(doc)
	doc.update({
		'doctype': 'Address'
	})
	address = frappe.get_doc(doc)
	address.save(ignore_permissions=True)

	return address