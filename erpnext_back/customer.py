from __future__ import unicode_literals
import frappe

from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import getdate, validate_email_add, today, add_years,add_days,format_datetime
from datetime import datetime
from frappe.model.naming import make_autoname
from frappe import throw, _, scrub
import frappe.permissions
from frappe.model.document import Document
import json
import collections
from erpnext.controllers.sales_and_purchase_return import make_return_doc
# import urllib
# import urllib2

@frappe.whitelist()
def test():
	return "test"

@frappe.whitelist()
def enableDisableOrder(names,disabled):
	if not frappe.has_permission("Customer", "write"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	names = json.loads(names)
	for name in names:
		so = frappe.get_doc("Customer", name)
		so.disabled=int(disabled)
		so.save()