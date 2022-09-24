import frappe

def execute():
	frappe.db.sql("""
		delete from `tabVersion`
		where ref_doctype in ('Stock Ledger Entry', 'GL Entry', 'Bin', 'Master Sales Order Item', 'Sales Order Item')
	""")
