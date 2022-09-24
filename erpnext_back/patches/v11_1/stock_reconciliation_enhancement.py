from __future__ import unicode_literals
import frappe

def execute():
	frappe.delete_doc_if_exists("Custom Script", "Stock Reconciliation-Client")

	for dt in ['Stock Reconciliation', 'Stock Reconciliation Item']:
		for name in frappe.get_all("Custom Field", filters={"dt": dt}):
			frappe.delete_doc("Custom Field", name.name)
		for name in frappe.get_all("Property Setter", filters={"doc_type": dt}):
			frappe.delete_doc("Property Setter", name.name)
