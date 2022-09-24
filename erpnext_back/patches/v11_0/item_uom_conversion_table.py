import frappe
from frappe.utils import flt

def execute():
	for f in ['purchase_pallets', 'sale_pallets', 'ppk_calculation', 'weight_of_pallets']:
		print("Converting Data/Read Only to Float Convertible for {0}: {1}".format("Item", f))
		frappe.db.sql("update `tabItem` set {0} = 0 where ifnull({0}, '') = '' or {0} = 'NaN'".format(f))

	frappe.reload_doc("stock", "doctype", "item")
	frappe.reload_doc("stock", "doctype", "uom_conversion_detail")
	frappe.reload_doc("stock", "doctype", "uom_conversion_graph")

	names = frappe.get_all("Item")
	for name in names:
		doc = frappe.get_doc("Item", name)
		for d in doc.uoms:
			if d.uom == doc.stock_uom:
				continue

			if abs(d.conversion_factor) >= 1:
				conv = doc.append("uom_conversion_graph", {
					"from_qty": flt(d.conversion_factor, doc.precision("to_qty", "uom_conversion_graph")),
					"from_uom": doc.stock_uom,
					"to_qty": 1.0,
					"to_uom": d.uom
				})
			else:
				conv = doc.append("uom_conversion_graph", {
					"from_qty": 1.0,
					"from_uom": doc.stock_uom,
					"to_qty": flt(1/flt(d.conversion_factor), doc.precision("to_qty", "uom_conversion_graph")),
					"to_uom": d.uom
				})
			conv.db_insert()
