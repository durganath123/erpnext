# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe
from frappe.utils import cint, fmt_money, flt, nowdate, getdate
from erpnext.accounts.doctype.pricing_rule.pricing_rule import get_pricing_rule_for_item
from erpnext.stock.doctype.batch.batch import get_batch_qty

def get_qty_in_stock(item_code, item_warehouse_field, warehouse=None):
	in_stock, stock_qty = 0, ''
	template_item_code, is_stock_item = frappe.db.get_value("Item", item_code, ["variant_of", "is_stock_item"])

	if not warehouse:
		warehouse = frappe.db.get_value("Item", item_code, item_warehouse_field)

	if not warehouse and template_item_code and template_item_code != item_code:
		warehouse = frappe.db.get_value("Item", template_item_code, item_warehouse_field)

	if warehouse:
		stock_qty = frappe.db.sql("""
			select GREATEST(S.actual_qty - S.reserved_qty - S.reserved_qty_for_production - S.reserved_qty_for_sub_contract, 0) / IFNULL(C.conversion_factor, 1)
			from tabBin S
			inner join `tabItem` I on S.item_code = I.Item_code
			left join `tabUOM Conversion Detail` C on I.sales_uom = C.uom and C.parent = I.Item_code
			where S.item_code=%s and S.warehouse=%s""", (item_code, warehouse))

		if stock_qty:
			stock_qty = adjust_qty_for_expired_items(item_code, stock_qty, warehouse)
			in_stock = stock_qty[0][0] > 0 and 1 or 0

	return frappe._dict({"in_stock": in_stock, "stock_qty": stock_qty, "is_stock_item": is_stock_item})


def adjust_qty_for_expired_items(item_code, stock_qty, warehouse):
	batches = frappe.get_all('Batch', filters=[{'item': item_code}], fields=['expiry_date', 'name'])
	expired_batches = get_expired_batches(batches)
	stock_qty = [list(item) for item in stock_qty]

	for batch in expired_batches:
		if warehouse:
			stock_qty[0][0] = max(0, stock_qty[0][0] - get_batch_qty(batch, warehouse))
		else:
			stock_qty[0][0] = max(0, stock_qty[0][0] - qty_from_all_warehouses(get_batch_qty(batch)))

		if not stock_qty[0][0]:
			break

	return stock_qty


def get_expired_batches(batches):
	"""
	:param batches: A list of dict in the form [{'expiry_date': datetime.date(20XX, 1, 1), 'name': 'batch_id'}, ...]
	"""
	return [b.name for b in batches if b.expiry_date and b.expiry_date <= getdate(nowdate())]


def qty_from_all_warehouses(batch_info):
	"""
	:param batch_info: A list of dict in the form [{u'warehouse': u'Stores - I', u'qty': 0.8}, ...]
	"""
	qty = 0
	for batch in batch_info:
		qty = qty + batch.qty

	return qty

def get_price(item_code, price_list, customer_group, company, qty=1, uom=None, date=None):
	from erpnext.stock.get_item_details import get_price_list_rate_for

	item = frappe.get_cached_doc("Item", item_code)
	price_list_doc = frappe.get_cached_doc("Price List", price_list)
	template_item_code = item.variant_of

	args = frappe._dict({
		"price_list": price_list,
		"uom": uom or item.sales_uom or item.stock_uom,
		"transaction_date": date or frappe.utils.today(),
		"qty": qty,
		"price_list_uom_dependant": not cint(price_list_doc.price_not_uom_dependant)
	})

	if price_list:
		price = get_price_list_rate_for(args, item_code)

		if template_item_code and not price:
			price = get_price_list_rate_for(args, template_item_code)

		if price:
			uom_margin = item.get("uom_additional_cost", {"uom": args.uom, "company": company})
			if not price_list_doc.get("prices_independent_of_additional_uom_cost") and uom_margin:
				price += flt(uom_margin[0].margin_rate)

			pricing_rule = get_pricing_rule_for_item(frappe._dict({
				"item_code": item_code,
				"qty": qty,
				"transaction_type": "selling",
				"price_list": price_list,
				"customer_group": customer_group,
				"company": company,
				"conversion_rate": 1,
				"for_shopping_cart": True,
				"currency": price_list_doc.currency
			}))

			if pricing_rule:
				if pricing_rule.pricing_rule_for == "Discount Percentage":
					price = flt(price * (1.0 - (flt(pricing_rule.discount_percentage) / 100.0)))

				if pricing_rule.pricing_rule_for == "Rate":
					price = pricing_rule.price_list_rate

			price_obj = frappe._dict({
				"price_list_rate": price,
				"currency": price_list_doc.currency
			})

			if price_obj:
				price_obj["formatted_price"] = fmt_money(price_obj["price_list_rate"], currency=price_obj["currency"])

				price_obj["currency_symbol"] = not cint(frappe.db.get_default("hide_currency_symbol")) \
					and (frappe.db.get_value("Currency", price_obj.currency, "symbol", cache=True) or price_obj.currency) \
					or ""

				price_obj["formatted_price_sales_uom"] = fmt_money(price_obj["price_list_rate"], currency=price_obj["currency"])

				if not price_obj["price_list_rate"]:
					price_obj["price_list_rate"] = 0

				if not price_obj["currency"]:
					price_obj["currency"] = ""

				if not price_obj["formatted_price"]:
					price_obj["formatted_price"] = ""

			return price_obj

def get_non_stock_item_status(item_code, item_warehouse_field):
#if item belongs to product bundle, check if bundle items are in stock
	if frappe.db.exists("Product Bundle", item_code):
		items = frappe.get_doc("Product Bundle", item_code).get_all_children()
		bundle_warehouse = frappe.db.get_value('Item', item_code, item_warehouse_field)
		return all([ get_qty_in_stock(d.item_code, item_warehouse_field, bundle_warehouse).in_stock for d in items ])
	else:
		return 1
