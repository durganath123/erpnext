from __future__ import unicode_literals
import frappe
from frappe import throw, _
import frappe.defaults
from frappe.utils import cint, flt, get_fullname, cstr
from erpnext.shopping_cart.cart import get_party


def get_context(context):
	context.no_cache = 1

	if frappe.session.user == "Guest":
		raise frappe.PermissionError("Please login first")

	party = get_party()
	default_items = frappe.get_all("Customer Default Item", fields=['item_code'],
		filters={"parenttype": 'Customer', "parent": party.name})

	items = []
	for d in default_items:
		items.append(frappe.get_cached_doc("Item", d.item_code))

	context["default_items"] = items


@frappe.whitelist()
def add_default_item(item_code):
	if item_code:
		party = get_party()
		party.append("default_items_tbl", {"item_code": item_code})
		party.flags.ignore_permissions = True
		party.save()

		context = {"item": frappe.get_cached_doc("Item", item_code)}

		return frappe.get_template("www/default-item-row.html").render(context)

@frappe.whitelist()
def remove_default_item(item_code):
	if item_code:
		party = get_party()
		row = party.get('default_items_tbl', filters={"item_code": item_code})

		for d in row:
			party.remove(d)

		party.flags.ignore_permissions = True
		party.save()

	return True
