# Copyright (c) 2017, Frappe and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt

from frappe.model.utils.rename_field import rename_field
from erpnext.stock.doctype.item_price.item_price import ItemPriceDuplicateItem

def execute():
	doctypes = [
		'Sales Order', 'Delivery Note', 'Sales Invoice',
		'Purchase Order', 'Purchase Receipt', 'Purchase Invoice',
		'Quotation', 'Supplier Quotation'
	]
	item_doctypes = [d + " Item" for d in doctypes]
	all_dts = doctypes + item_doctypes + ['Item']
	quoted_dts = ["'" + dt + "'" for dt in all_dts]
	quoted_dts_without_item = ["'" + dt + "'" for dt in doctypes + item_doctypes]

	# Convert Data/Read Only fields to Float
	for dt in doctypes:
		if frappe.get_meta(dt).has_field('total_boxes'):
			print("Converting Data/Read Only to Float Convertible for {0}: {1}".format(dt, 'total_boxes'))
			frappe.db.sql("update `tab{0}` set total_boxes = total_qty where ifnull(total_boxes, '') = '' or total_boxes = 'NaN'".format(dt))

		for f in ['total_pallet', 'total_pallets', 'total_gross_weight_lbs', 'delivery_charges']:
			df = frappe.get_meta(dt).get_field(f)
			if df and df.fieldtype != 'Float':
				print("Converting Data/Read Only to Float Convertible for {0}: {1}".format(dt, f))
				frappe.db.sql("update `tab{0}` set {1} = 0 where ifnull({1}, '') = '' or {1} = 'NaN'".format(dt, f))

	for dt in item_doctypes:
		for f in ['sale_pallets', 'boxes_pallet_for_purchase']:
			df = frappe.get_meta(dt).get_field(f)
			if df and df.fieldtype != 'Float':
				print("Converting Data/Read Only to Float Convertible for {0}: {1}".format(dt, f))
				frappe.db.sql("update `tab{0}` set {1} = 0 where ifnull({1}, '') = '' or {1} = 'NaN'".format(dt, f))

	old_meta = {}
	for dt in all_dts:
		old_meta[dt] = frappe.get_meta(dt)

	# Load updated DocType
	print("Reloading DocTypes")
	frappe.reload_doc('stock', 'doctype', 'item', force=1)
	frappe.reload_doc('stock', 'doctype', 'uom_additional_cost', force=1)
	frappe.reload_doc('stock', 'doctype', 'landed_cost_voucher', force=1)
	frappe.reload_doc('stock', 'doctype', 'landed_cost_item', force=1)
	frappe.reload_doc('selling', 'doctype', 'quotation', force=1)
	frappe.reload_doc('selling', 'doctype', 'quotation_item', force=1)
	frappe.reload_doc('selling', 'doctype', 'sales_order', force=1)
	frappe.reload_doc('selling', 'doctype', 'sales_order_item', force=1)
	frappe.reload_doc('stock', 'doctype', 'delivery_note', force=1)
	frappe.reload_doc('stock', 'doctype', 'delivery_note_item', force=1)
	frappe.reload_doc('accounts', 'doctype', 'sales_invoice', force=1)
	frappe.reload_doc('accounts', 'doctype', 'sales_invoice_item', force=1)
	frappe.reload_doc('buying', 'doctype', 'supplier_quotation', force=1)
	frappe.reload_doc('buying', 'doctype', 'supplier_quotation_item', force=1)
	frappe.reload_doc('buying', 'doctype', 'purchase_order', force=1)
	frappe.reload_doc('buying', 'doctype', 'purchase_order_item', force=1)
	frappe.reload_doc('stock', 'doctype', 'purchase_receipt', force=1)
	frappe.reload_doc('stock', 'doctype', 'purchase_receipt_item', force=1)
	frappe.reload_doc('accounts', 'doctype', 'purchase_invoice', force=1)
	frappe.reload_doc('accounts', 'doctype', 'purchase_invoice_item', force=1)
	frappe.reload_doc('stock', 'doctype', 'stock_entry_detail', force=1)

	# Rename fields
	for dt in ['Item']:
		for old, new in [('cost_center', 'selling_cost_center')]:
			print("Rename Field in {0}: {1} -> {2}".format(dt, old, new))
			rename_field(dt, old, new)

	for dt in ['Landed Cost Voucher']:
		for old, new in [('total_weight', 'total_alt_uom_qty')]:
			print("Rename Field in {0}: {1} -> {2}".format(dt, old, new))
			rename_field(dt, old, new)
	for dt in ['Landed Cost Item']:
		for old, new in [('weight', 'alt_uom_qty')]:
			print("Rename Field in {0}: {1} -> {2}".format(dt, old, new))
			rename_field(dt, old, new)

	for dt in doctypes:
		for old, new in [('total_net_weight', 'total_gross_weight'), ('total_pallet', 'total_pallets')]:
			if old_meta[dt].has_field(old) and not old_meta[dt].has_field(new):
				print("Rename Field in {0}: {1} -> {2}".format(dt, old, new))
				rename_field(dt, old, new)

	for dt in item_doctypes:
		for old, new in [('sale_pallets', 'qty_per_pallet'), ('boxes_pallet_for_purchase', 'qty_per_pallet'), ('boxes_ordered', 'qty_ordered'), ('is_authorize', 'requires_authorization')]:
			if old_meta[dt].has_field(old) and not old_meta[dt].has_field(new):
				print("Rename Field in {0}: {1} -> {2}".format(dt, old, new))
				rename_field(dt, old, new)

	# Item Master
	print("Item")
	for item in frappe.db.sql("select name, gross_weight from tabItem", as_dict=1):
		doc = frappe.get_doc('Item', item.name)
		doc.weight_uom = 'lbs'
		doc.alt_uom = doc.weight_uom if doc.weight_uom != doc.stock_uom else "lbs"
		doc.alt_uom_size = flt(doc.weight_per_unit) or 1
		doc.weight_per_unit = item.gross_weight
		doc.save()

	# Item Price
	print("Item Price")
	for name in frappe.get_all('Item Price', order_by=('creation desc')):
		doc = frappe.get_doc('Item Price', name)
		try:
			doc.update_item_details()
			doc.check_duplicates()
			doc.db_update()
		except ItemPriceDuplicateItem:
			print("Item Price ({0}) for Item ({1}) is duplicate".format(doc.name, doc.item_code))

	# Transactions
	for dt in doctypes:
		print(dt)

		# Item Per Unit from Old Net Weight
		if frappe.get_meta(dt + " Item").has_field('stock_alt_uom_size'):
			frappe.db.sql("""
				update `tab{dt} Item` set
					stock_alt_uom_size = if(weight_per_unit=0, 1, weight_per_unit) / if(conversion_factor=0, 1, conversion_factor),
					stock_alt_uom_size_std = if(weight_per_unit=0, 1, weight_per_unit) / if(conversion_factor=0, 1, conversion_factor),
					alt_uom_size_std = if(weight_per_unit=0, 1, weight_per_unit)
			""".format(dt=dt))
		else:
			print("DocType {dt} Item does not have field stock_alt_uom_size".format(dt=dt))

		frappe.db.sql("""
			update `tab{dt} Item` set
				alt_uom_size = if(weight_per_unit=0, 1, weight_per_unit),
				alt_uom = weight_uom
		""".format(dt=dt))

		# Item Gross Weight Per Unit
		if old_meta[dt + " Item"].has_field('gross_weight_lbs'):
			frappe.db.sql("""update `tab{dt} Item` set weight_per_unit = gross_weight_lbs""".format(dt=dt))
		else:
			print("DocType {dt} Item does not have field gross_weight_lbs".format(dt=dt))

		# Item Packed In Qty
		if frappe.get_meta(dt + " Item").has_field('boxes'):
			frappe.db.sql("""update `tab{dt} Item` set boxes = qty""".format(dt=dt))
		else:
			print("DocType {dt} Item does not have field boxes".format(dt=dt))

		# Item # of pallets
		if frappe.get_meta(dt + " Item").has_field('pallets'):
			frappe.db.sql("""update `tab{dt} Item` set pallets = IF(qty_per_pallet=0, 0, qty/qty_per_pallet)""".format(dt=dt))
		else:
			print("DocType {dt} Item does not have field pallets".format(dt=dt))

		# Item Contents Qty and Gross Weight
		frappe.db.sql("""
			update `tab{dt} Item` set
				alt_uom_qty = alt_uom_size * qty,
				total_weight = weight_per_unit * stock_qty
		""".format(dt=dt))

		if frappe.get_meta(dt + " Item").has_field('total_weight_kg'):
			frappe.db.sql("""update `tab{dt} Item` set total_weight_kg = total_weight * 0.45359237""".format(dt=dt))
		else:
			print("DocType {dt} Item does not have field total_weight_kg".format(dt=dt))

		# Items without Contents UOM
		frappe.db.sql("""
			update `tab{dt} Item`
			set alt_uom_size = 1, alt_uom_qty = stock_qty
			where ifnull(alt_uom, '') = ''
		""".format(dt=dt))

		if frappe.get_meta(dt + " Item").has_field('stock_alt_uom_size'):
			frappe.db.sql("""
				update `tab{dt} Item`
				set
					stock_alt_uom_size = 1/conversion_factor,
					stock_alt_uom_size_std = 1/conversion_factor,
					alt_uom_size_std = 1
				where ifnull(alt_uom, '') = ''
			""".format(dt=dt))

		# Item Contents Rate
		if frappe.get_meta(dt + " Item").has_field('alt_uom_rate'):
			frappe.db.sql("""
				update `tab{dt} Item` i
				inner join `tab{dt}` m on m.name = i.parent
				set
					i.alt_uom_rate = i.amount / if(i.alt_uom_qty = 0, if(i.qty=0, 1, i.qty), i.alt_uom_qty),
					i.base_alt_uom_rate = i.amount * m.conversion_rate / if(i.alt_uom_qty = 0, if(i.qty=0, 1, i.qty), i.alt_uom_qty)
			""".format(dt=dt))
		else:
			print("DocType {dt} Item does not have field alt_uom_rate".format(dt=dt))

		# Parent Total Contents Qty
		frappe.db.sql("""
			update `tab{dt}` m
			set total_alt_uom_qty = (
				select ifnull(sum(d.alt_uom_qty), 0)
				from `tab{dt} Item` d where d.parent = m.name and d.parenttype = '{dt}'
			)
		""".format(dt=dt))

		# Parent Total Gross Weight
		if old_meta[dt].has_field('total_gross_weight_lbs'):
			frappe.db.sql("update `tab{dt}` m set total_gross_weight = total_gross_weight_lbs".format(dt=dt))
		else:
			print("DocType {dt} does not have field total_gross_weight_lbs".format(dt=dt))

		if frappe.get_meta(dt).has_field('total_gross_weight_kg'):
			frappe.db.sql("update `tab{dt}` set total_gross_weight_kg = total_gross_weight * 0.45359237".format(dt=dt))

		# Parent Total Taxes
		if frappe.get_meta(dt).has_field('total_taxes'):
			frappe.db.sql("""update `tab{dt}` set total_taxes = total_taxes_and_charges""".format(dt=dt))
		else:
			print("DocType {dt} does not have field total_taxes".format(dt=dt))

		# Sales Order Title and Authorization
		if dt == "Sales Order":
			frappe.db.sql("update `tab{dt}` m set title = ifnull(customer_name, customer)".format(dt=dt))
			frappe.db.sql("update `tab{dt}` m set authorize = 'Not Required' where ifnull(authorize, '') = ''".format(dt=dt))

	# Stock Entry special case
	print("Stock Entry")
	frappe.db.sql("""
		update `tabStock Entry Detail`
		set alt_uom_size = 1, alt_uom_qty = transfer_qty
		where ifnull(alt_uom, '') = ''
	""")

	# Remove customizations
	print("Remove Custom Fields and Property Setters")
	custom_fields = frappe.db.sql_list("select name from `tabCustom Field` where dt in ({0})".format(", ".join(quoted_dts)))
	prop_setters = frappe.db.sql_list("select name from `tabProperty Setter` where doc_type in ({0})".format(", ".join(quoted_dts)))
	for name in custom_fields:
		frappe.delete_doc('Custom Field', name)
	for name in prop_setters:
		frappe.delete_doc('Property Setter', name)

	custom_scripts = frappe.db.sql_list("select name from `tabCustom Script` where dt in ({0})".format(", ".join(quoted_dts)))
	for name in custom_scripts:
		frappe.delete_doc('Custom Script', name)
