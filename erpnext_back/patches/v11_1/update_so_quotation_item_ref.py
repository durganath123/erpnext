from __future__ import unicode_literals
import frappe


def execute():
	frappe.reload_doc('selling', 'doctype', 'sales_order_item')

	so_items = frappe.db.sql("""
		select name, parent, item_code, prevdoc_docname
		from `tabSales Order Item`
		where ifnull(quotation_item, '') = '' and ifnull(prevdoc_docname, '') != ''
	""", as_dict=1)

	quotation_names = list(set([d.prevdoc_docname for d in so_items]))

	quotation_map = {}
	for name in quotation_names:
		doc = frappe.get_doc("Quotation", name)
		quotation_dict = quotation_map.setdefault(doc.name, {})
		for d in doc.items:
			quotation_dict[d.item_code] = d.name

	for d in so_items:
		ref_name = quotation_map.get(d.prevdoc_docname, {}).get(d.item_code)
		if not ref_name:
			print("Sales Order {0}, Item {1}, Against Quotation {2}: Reference row not found".format(d.parent, d.item_code, d.prevdoc_docname))
		else:
			frappe.db.set_value("Sales Order Item", d.name, "quotation_item", ref_name)
