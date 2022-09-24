# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from six import iteritems

def execute():
	frappe.reload_doc("stock", "doctype", "purchase_receipt")
	frappe.reload_doc("accounts", "doctype", "purchase_invoice")

	po_map = dict(frappe.db.sql("select name, shipping_date from `tabPurchase Order` where docstatus<2"))

	precs = frappe.db.sql("select distinct parent, purchase_order from `tabPurchase Receipt Item` where docstatus<2", as_dict=1)
	pinvs = frappe.db.sql("select distinct parent, purchase_order from `tabPurchase Invoice Item` where docstatus<2", as_dict=1)

	prec_map = {}
	for d in precs:
		prec_map.setdefault(d.parent, []).append(d.purchase_order)

	pinv_map = {}
	for d in pinvs:
		pinv_map.setdefault(d.parent, []).append(d.purchase_order)

	for name, pos in iteritems(prec_map):
		if len(pos) == 1:
			shipping_date = po_map.get(pos[0])
			if shipping_date:
				frappe.db.set_value("Purchase Receipt", name, "shipping_date", shipping_date)

	for name, pos in iteritems(pinv_map):
		if len(pos) == 1:
			shipping_date = po_map.get(pos[0])
			if shipping_date:
				frappe.db.set_value("Purchase Invoice", name, "shipping_date", shipping_date)
