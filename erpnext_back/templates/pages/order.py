# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

from frappe import _
from erpnext.shopping_cart.doctype.shopping_cart_settings.shopping_cart_settings import show_attachments
from erpnext.shopping_cart.cart import can_copy_items

def get_context(context):
	context.no_cache = 1
	context.show_sidebar = False
	context.doc = frappe.get_doc(frappe.form_dict.doctype, frappe.form_dict.name)

	add_linked_documents(context)
	decorate_doc(context.doc)
	context.can_copy_items = can_copy_items(context.doc)

	if hasattr(context.doc, "set_indicator"):
		context.doc.set_indicator()

	if show_attachments():
		context.attachments = get_attachments(frappe.form_dict.doctype, frappe.form_dict.name)

	context.parents = frappe.form_dict.parents
	context.title = frappe.form_dict.name
	context.payment_ref = frappe.db.get_value("Payment Request",
		{"reference_name": frappe.form_dict.name}, "name")

	context.enabled_checkout = frappe.get_doc("Shopping Cart Settings").enable_checkout

	default_print_format = frappe.db.get_value('Property Setter', dict(property='default_print_format', doc_type=frappe.form_dict.doctype), "value")
	if default_print_format:
		context.print_format = default_print_format
	else:
		context.print_format = "Standard"

	if not frappe.has_website_permission(context.doc):
		frappe.throw(_("Not Permitted"), frappe.PermissionError)
	
	# check for the loyalty program of the customer
	customer_loyalty_program = frappe.db.get_value("Customer", context.doc.customer, "loyalty_program")	
	if customer_loyalty_program:
		from erpnext.accounts.doctype.loyalty_program.loyalty_program import get_loyalty_program_details_with_points
		loyalty_program_details = get_loyalty_program_details_with_points(context.doc.customer, customer_loyalty_program)
		context.available_loyalty_points = int(loyalty_program_details.get("loyalty_points"))


def add_linked_documents(context):
	if context.doc.doctype == "Quotation":
		sales_orders = frappe.db.sql_list("""
			select distinct parent
			from `tabSales Order Item`
			where prevdoc_docname = %s and docstatus < 2
		""", context.doc.name)

		context["sales_orders"] = sales_orders

	if context.doc.doctype == "Sales Order":
		quotations = list(set([item.prevdoc_docname for item in context.doc.items if item.prevdoc_docname]))
		context["quotations"] = quotations

		back_orders = frappe.db.sql_list("""
			select distinct back_order
			from `tabQty Adjustment Log`
			where sales_order = %s and ifnull(back_order, '') != ''
		""", context.doc.name)
		context["back_orders"] = back_orders


def decorate_doc(doc):
	for d in doc.get('items', []):
		d.update(frappe.get_cached_value("Item", d.item_code,
			["thumbnail", "website_image", "description", "route"], as_dict=True))

	return doc


def get_attachments(dt, dn):
	return frappe.get_all("File",
		fields=["name", "file_name", "file_url", "is_private"],
		filters={"attached_to_name": dn, "attached_to_doctype": dt, "is_private": 0})
