# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, nowdate, getdate, formatdate, today
from frappe import _

from erpnext.controllers.selling_controller import SellingController

form_grid_templates = {
	"items": "templates/form_grid/item_grid.html"
}

class Quotation(SellingController):
	def __setup__(self):
		super(Quotation, self).__setup__()
		self.cart_warnings = []
		self.cart_errors = []

	def set_indicator(self):
		if self.docstatus==1:
			if self.status == "Ordered":
				self.indicator_color = 'green'
				self.indicator_title = 'Confirmed'
			else:
				self.indicator_color = 'yellow'
				self.indicator_title = 'Received by {0}'.format(self.company.split(" ")[0])

			if self.valid_till and getdate(self.valid_till) < getdate(nowdate()):
				self.indicator_color = 'darkgrey'
				self.indicator_title = 'Expired'
		else:
			if self.confirmed_by_customer:
				self.indicator_color = 'orange'
				self.indicator_title = 'Sent to {0}'.format(self.company.split(" ")[0])
			else:
				self.indicator_color = 'red'
				self.indicator_title = 'Draft'


	def validate(self):
		if self.flags.cart_quotation:
			self.validate_delivery_date(lower_limit=self.transaction_date, throw=False, set_null=True)
			self.validate_delivery_date_holiday(throw=False, set_null=True)

		super(Quotation, self).validate()
		self.set_status()
		self.update_opportunity()
		self.validate_uom_is_integer("stock_uom", "qty")
		self.validate_valid_till()
		self.set_customer_name()
		if self.items:
			self.with_items = 1

	def get_cart_messages(self):
		self.get_cart_errors()
		self.get_cart_warnings()

	def get_cart_warnings(self):
		if self.delivery_date:
			same_date_quotations = frappe.get_all("Quotation", filters={
				"name": ['!=', self.name],
				"docstatus": ['<', 2],
				"quotation_to": "Customer",
				"customer": self.customer,
				"delivery_date": self.delivery_date,
			})
			if same_date_quotations:
				links = ["<b><a href='/purchase-orders/{0}' target='_blank'>{0}</a></b>".format(d.name) for d in same_date_quotations]
				self.cart_warnings.append(_("Purchase Orders already exist for Delivery Date {0}: {1}")
					.format(formatdate(self.delivery_date, "EEE, MMMM d, Y"), ", ".join(links)))

			same_date_sales_orders = frappe.get_all("Sales Order", filters={
				"docstatus": ['<', 2],
				"customer": self.customer,
				"delivery_date": self.delivery_date
			})
			if same_date_sales_orders:
				links = ["<b><a href='/sales-orders/{0}' target='_blank'>{0}</a></b>".format(d.name) for d in same_date_sales_orders]
				self.cart_warnings.append(_("Sales Orders already exist for Delivery Date {0}: {1}")
					.format(formatdate(self.delivery_date, "EEE, MMMM d, Y"), ", ".join(links)))

	def get_cart_errors(self):
		self.validate_delivery_date(lower_limit=today(), throw=False, set_null=False)
		self.validate_delivery_date_holiday(throw=False, set_null=False)

		if self.delivery_date:
			if not self.items:
				self.cart_errors.append(_("Please add items to order"))
			elif not self.total_qty:
				self.cart_errors.append(_("Please set item quantities"))

			if not self.customer_address:
				self.cart_errors.append(_("Please select address"))
		else:
			self.cart_errors.append(_("Please select Delivery Date"))

	def remove_zero_qty_items(self):
		to_remove = self.get('items', filters={"qty": 0})
		for d in to_remove:
			self.remove(d)
			
	def validate_valid_till(self):
		if self.valid_till and getdate(self.valid_till) < getdate(self.transaction_date):
			frappe.throw(_("Valid till date cannot be before transaction date"))

	def validate_delivery_date(self, lower_limit, throw, set_null):
		if self.delivery_date and getdate(self.delivery_date) < getdate(lower_limit):
			message = _("Delivery Date <b>{0}</b> cannot be before Order Date").format(
				formatdate(self.delivery_date, "EEE, MMMM d, Y"))

			if throw:
				frappe.throw(message)

			self.cart_errors.append(message)

			if set_null:
				self.delivery_date = None

	def validate_delivery_date_holiday(self, throw, set_null):
		if self.delivery_date:
			holiday_list_name = frappe.get_cached_value("Company", self.company, "default_holiday_list")
			if holiday_list_name:
				holiday_list = frappe.get_cached_doc("Holiday List", holiday_list_name)
				holiday_row = holiday_list.get('holidays', filters={'holiday_date': getdate(self.delivery_date)})
				if holiday_row:
					holiday_row = holiday_row[0]
					message = _("Delivery Date <b>{0}</b> cannot be selected due to <b>{1}</b> holiday").format(
						formatdate(self.delivery_date, "EEE, MMMM d, Y"), holiday_row.description)

					if throw:
						frappe.throw(message)

					self.cart_errors.append(message)

					if set_null:
						self.delivery_date = None

	def has_sales_order(self):
		return frappe.db.get_value("Sales Order Item", {"prevdoc_docname": self.name, "docstatus": ['<', 2]})

	def update_lead(self):
		if self.quotation_to == "Lead" and self.party_name:
			frappe.get_doc("Lead", self.party_name).set_status(update=True)

	def set_customer_name(self):
		if self.party_name and self.quotation_to == 'Customer':
			self.customer_name = frappe.db.get_value("Customer", self.party_name, "customer_name")
		elif self.party_name and self.quotation_to == 'Lead':
			lead_name, company_name = frappe.db.get_value("Lead", self.party_name, ["lead_name", "company_name"])
			self.customer_name = company_name or lead_name

	def update_opportunity(self):
		for opportunity in list(set([d.prevdoc_docname for d in self.get("items")])):
			if opportunity:
				self.update_opportunity_status(opportunity)

		if self.opportunity:
			self.update_opportunity_status()

	def update_opportunity_status(self, opportunity=None):
		if not opportunity:
			opportunity = self.opportunity

		opp = frappe.get_doc("Opportunity", opportunity)
		opp.set_status(update=True)

	def declare_enquiry_lost(self, lost_reasons_list, detailed_reason=None):
		if not self.has_sales_order():
			frappe.db.set(self, 'status', 'Lost')

			if detailed_reason:
				frappe.db.set(self, 'order_lost_reason', detailed_reason)

			for reason in lost_reasons_list:
				self.append('lost_reasons', reason)

			self.update_opportunity()
			self.update_lead()
			self.save()

		else:
			frappe.throw(_("Cannot set as Lost as Sales Order is made."))

	def on_submit(self):
		# Check for Approving Authority
		frappe.get_doc('Authorization Control').validate_approving_authority(self.doctype,
			self.company, self.base_grand_total, self)

		self.validate_delivery_date(lower_limit=self.transaction_date, throw=True, set_null=False)
		self.validate_delivery_date_holiday(throw=True, set_null=False)

		#update enquiry status
		self.update_opportunity()
		self.update_lead()

	def before_submit(self):
		self.validate_confirmed_by_customer()

	def validate_confirmed_by_customer(self):
		if self.order_type == "Shopping Cart" and not self.confirmed_by_customer:
			frappe.throw(_("Order not yet confirmed by customer"))

	def on_cancel(self):
		super(Quotation, self).on_cancel()

		#update enquiry status
		self.set_status(update=True)
		self.update_opportunity()
		self.update_lead()

	def print_other_charges(self,docname):
		print_lst = []
		for d in self.get('taxes'):
			lst1 = []
			lst1.append(d.description)
			lst1.append(d.total)
			print_lst.append(lst1)
		return print_lst

	def on_recurring(self, reference_doc, auto_repeat_doc):
		self.valid_till = None

def get_list_context(context=None):
	from erpnext.controllers.website_list_for_contact import get_list_context
	list_context = get_list_context(context)
	list_context.update({
		'show_sidebar': False,
		'show_search': True,
		'no_breadcrumbs': False,
		'title': _('Purchase Orders'),
		'order_by': 'delivery_date desc, transaction_date desc'
	})

	return list_context

@frappe.whitelist()
def make_sales_order(source_name, target_doc=None):
	quotation = frappe.db.get_value("Quotation", source_name, ["transaction_date", "valid_till"], as_dict = 1)
	if quotation.valid_till and (quotation.valid_till < quotation.transaction_date or quotation.valid_till < getdate(nowdate())):
		frappe.throw(_("Validity period of this quotation has ended."))

	sales_order = frappe.get_all("Sales Order Item", fields='distinct parent', filters={"prevdoc_docname": source_name, "docstatus": ['<', 2]})
	if sales_order:
		sales_order_name = [frappe.get_desk_link("Sales Order", d.parent) for d in sales_order]
		frappe.throw(_("Sales Order already exists: {0}").format(", ".join(sales_order_name)))

	return _make_sales_order(source_name, target_doc)

def _make_sales_order(source_name, target_doc=None, ignore_permissions=False):
	customer = _make_customer(source_name, ignore_permissions)

	def set_missing_values(source, target):
		if customer:
			target.customer = customer.name
			target.customer_name = customer.customer_name
		if source.referral_sales_partner:
			target.sales_partner=source.referral_sales_partner
			target.commission_rate=frappe.get_value('Sales Partner', source.referral_sales_partner, 'commission_rate')
		# target.ignore_pricing_rule = 1
		target.flags.ignore_permissions = ignore_permissions
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

	def update_item(obj, target, source_parent):
		target.stock_qty = flt(obj.qty) * flt(obj.conversion_factor)

	doclist = get_mapped_doc("Quotation", source_name, {
			"Quotation": {
				"doctype": "Sales Order",
				"field_map": {
					"delivery_date": "delivery_date"
				},
				"validation": {
					"docstatus": ["=", 1]
				}
			},
			"Quotation Item": {
				"doctype": "Sales Order Item",
				"field_map": {
					"parent": "prevdoc_docname",
					"name": "quotation_item"
				},
				"postprocess": update_item
			},
			"Sales Taxes and Charges": {
				"doctype": "Sales Taxes and Charges",
				"add_if_empty": True
			},
			"Sales Team": {
				"doctype": "Sales Team",
				"add_if_empty": True
			},
			"Payment Schedule": {
				"doctype": "Payment Schedule",
				"add_if_empty": True
			}
		}, target_doc, set_missing_values, ignore_permissions=ignore_permissions)

	# postprocess: fetch shipping address, set missing values

	return doclist

def set_expired_status():
	frappe.db.sql("""
		UPDATE
			`tabQuotation` SET `status` = 'Expired'
		WHERE
			`status` not in ('Ordered', 'Expired', 'Lost', 'Cancelled') AND `valid_till` < %s
		""", (nowdate()))

@frappe.whitelist()
def make_sales_invoice(source_name, target_doc=None):
	return _make_sales_invoice(source_name, target_doc)

def _make_sales_invoice(source_name, target_doc=None, ignore_permissions=False):
	customer = _make_customer(source_name, ignore_permissions)

	def set_missing_values(source, target):
		if customer:
			target.customer = customer.name
			target.customer_name = customer.customer_name
		# target.ignore_pricing_rule = 1
		target.flags.ignore_permissions = ignore_permissions
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

	def update_item(obj, target, source_parent):
		target.cost_center = None
		target.stock_qty = flt(obj.qty) * flt(obj.conversion_factor)

	doclist = get_mapped_doc("Quotation", source_name, {
			"Quotation": {
				"doctype": "Sales Invoice",
				"validation": {
					"docstatus": ["=", 1]
				}
			},
			"Quotation Item": {
				"doctype": "Sales Invoice Item",
				"postprocess": update_item
			},
			"Sales Taxes and Charges": {
				"doctype": "Sales Taxes and Charges",
				"add_if_empty": True
			},
			"Sales Team": {
				"doctype": "Sales Team",
				"add_if_empty": True
			}
		}, target_doc, set_missing_values, ignore_permissions=ignore_permissions)

	return doclist

def _make_customer(source_name, ignore_permissions=False):
	quotation = frappe.db.get_value("Quotation",
		source_name, ["order_type", "party_name", "customer_name"], as_dict=1)

	if quotation and quotation.get('party_name'):
		if not frappe.db.exists("Customer", quotation.get("party_name")):
			lead_name = quotation.get("party_name")
			customer_name = frappe.db.get_value("Customer", {"lead_name": lead_name},
				["name", "customer_name"], as_dict=True)
			if not customer_name:
				from erpnext.crm.doctype.lead.lead import _make_customer
				customer_doclist = _make_customer(lead_name, ignore_permissions=ignore_permissions)
				customer = frappe.get_doc(customer_doclist)
				customer.flags.ignore_permissions = ignore_permissions
				if quotation.get("party_name") == "Shopping Cart":
					customer.customer_group = frappe.db.get_value("Shopping Cart Settings", None,
						"default_customer_group")

				try:
					customer.insert()
					return customer
				except frappe.NameError:
					if frappe.defaults.get_global_default('cust_master_name') == "Customer Name":
						customer.run_method("autoname")
						customer.name += "-" + lead_name
						customer.insert()
						return customer
					else:
						raise
				except frappe.MandatoryError:
					frappe.local.message_log = []
					frappe.throw(_("Please create Customer from Lead {0}").format(lead_name))
			else:
				return customer_name
		else:
			return frappe.get_doc("Customer", quotation.get("party_name"))
