# Copyright (c) 2018, Frappe and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
import datetime


def execute():
	frappe.reload_doctype("Sales Order")
	frappe.reload_doctype("Sales Order Item")
	frappe.reload_doctype("Delivery Note")
	frappe.reload_doctype("Delivery Note Item")
	frappe.reload_doctype("Sales Invoice")
	frappe.reload_doctype("Sales Invoice Item")

	frappe.reload_doctype("Purchase Order")
	frappe.reload_doctype("Purchase Order Item")
	frappe.reload_doctype("Purchase Receipt")
	frappe.reload_doctype("Purchase Receipt Item")
	frappe.reload_doctype("Purchase Invoice")
	frappe.reload_doctype("Purchase Invoice Item")

	frappe.db.auto_commit_on_many_writes = 1

	print("Updating Billing Status")
	start_time = datetime.datetime.now()

	frappe.db.sql("update `tabItem` set tolerance = 0")
	frappe.db.set_value("Stock Settings", None, "tolerance", 1e+38)

	update_return_against_item_detail()

	frappe.flags.ignore_qty_validation_in_status_updater = 1

	trigger_dn()
	trigger_prec()
	trigger_pinv()
	trigger_sinv()

	frappe.db.set_value("Stock Settings", None, "tolerance", 0)

	end_time = datetime.datetime.now()
	print("Billing Status updated in {0}".format(end_time-start_time))


def update_return_against_item_detail():
	print("Updating Return Against Item Detail")
	for dt, detail_field in [('Delivery Note', 'dn_detail'), ('Purchase Receipt', 'pr_detail')]:
		returns = frappe.get_all(dt, filters={"is_return": 1, "docstatus": 1}, fields=['name', 'return_against'])
		return_against_unique = list(set([d.return_against for d in returns]))
		return_names_unique = [d.name for d in returns]

		# Get Data
		source_data = frappe.db.sql("""
			select parent, name, item_code, qty
			from `tab{0} Item`
			where parent in ({1})
		""".format(dt, ", ".join(["%s"] * len(return_against_unique))), return_against_unique, as_dict=1) if return_against_unique else []

		return_data = frappe.db.sql("""
			select parent, name, item_code, qty
			from `tab{0} Item`
			where parent in ({1})
		""".format(dt, ", ".join(["%s"] * len(return_names_unique))), return_names_unique, as_dict=1) if return_names_unique else []

		# Format Data
		source_map = {}
		for d in source_data:
			source_map.setdefault(d.parent, {}).setdefault(d.item_code, []).append(d)

		return_map = {}
		for d in return_data:
			return_map.setdefault(d.parent, []).append(d)

		# Build return ledger and update
		for return_doc in returns:
			source_items = source_map[return_doc.return_against]
			return_items = return_map[return_doc.name]

			for return_row in return_items:
				if return_row.item_code not in source_items:
					print("Item {0} in {1} not in {2}".format(return_row.item_code, return_doc.name, return_doc.return_against))
				else:
					valid_source = None
					for source_row in source_items[return_row.item_code]:
						if return_row.qty <= source_row.qty:
							source_row.qty -= return_row.qty
							valid_source = source_row
							break

					if valid_source:
						frappe.db.sql("update `tab{0} Item` set {1} = %s where name = %s".format(dt, detail_field),
							[valid_source.name, return_row.name])
					else:
						print("Valid Source not found for Item {0} in {1} return against {2}".format(return_row.item_code, return_doc.name, return_doc.return_against))


def trigger_sinv():
	print("Triggering SINV")
	si_names = frappe.get_all("Sales Invoice", {"docstatus": 1})
	for name in si_names:
		name = name.name
		doc = frappe.get_doc("Sales Invoice", name)
		doc.update_status_updater_args()
		doc.update_prevdoc_status()
		if not doc.is_return:
			doc.update_billing_status_for_zero_amount_refdoc("Sales Order")
		doc.clear_cache()


def trigger_pinv():
	print("Triggering PINV")
	pi_names = frappe.get_all("Purchase Invoice", {"docstatus": 1})
	for name in pi_names:
		name = name.name
		doc = frappe.get_doc("Purchase Invoice", name)
		doc.update_status_updater_args()
		doc.update_prevdoc_status()
		if not doc.is_return:
			doc.update_billing_status_for_zero_amount_refdoc("Purchase Order")
		doc.clear_cache()


def trigger_dn():
	print("Triggering DN")
	dn_names = frappe.get_all("Delivery Note", {"docstatus": 1})
	for name in dn_names:
		name = name.name
		doc = frappe.get_doc("Delivery Note", name)
		doc.update_prevdoc_status()
		doc.clear_cache()


def trigger_prec():
	print("Triggering PREC")
	pr_names = frappe.get_all("Purchase Receipt", {"docstatus": 1})
	for name in pr_names:
		name = name.name
		doc = frappe.get_doc("Purchase Receipt", name)
		doc.update_prevdoc_status()
		doc.clear_cache()
