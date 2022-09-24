# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, cint, getdate

def execute(filters=None):
	if not filters: filters = {}

	db_qty_precision = 6 if cint(frappe.db.get_default("float_precision")) <= 6 else 9
	value_precision = frappe.get_precision("Stock Ledger Entry", "stock_value")

	columns = get_columns(filters)
	item_map = get_item_details(filters)
	iwb_map = get_item_warehouse_batch_map(filters)

	data = []
	for item in sorted(iwb_map):
		for wh in sorted(iwb_map[item]):
			for batch in sorted(iwb_map[item][wh]):
				qty_dict = iwb_map[item][wh][batch]
				if flt(qty_dict.bal_qty, db_qty_precision) or flt(qty_dict.bal_val, value_precision) or not filters.get('hide_empty_batches'):
					if qty_dict.opening_qty or qty_dict.opening_val or qty_dict.in_qty or qty_dict.in_val or qty_dict.out_qty or qty_dict.out_val or qty_dict.bal_qty or qty_dict.bal_val:
						row = {
							"item_code": item,
							"item_name": item_map[item]["item_name"],
							"description": item_map[item]["description"],
							"warehouse": wh,
							"batch_no": batch,
							"stock_uom": item_map[item]["stock_uom"]
						}
						row.update(qty_dict)
						data.append(row)

	return columns, data

def get_columns(filters):
	"""return columns based on filters"""
	columns = [
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 100},
		{"label": _("Item Name"), "fieldname": "item_name", "width": 150},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 100},
		{"label": _("Batch"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 100},
		{"label": _("Stock UOM"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 90},
		{"label": _("Opening Qty"), "fieldname": "opening_qty", "fieldtype": "Float", "width": 100, "convertible": "qty"},
		{"label": _("Opening Value"), "fieldname": "opening_val", "fieldtype": "Float", "width": 110},
		{"label": _("In Qty"), "fieldname": "in_qty", "fieldtype": "Float", "width": 80, "convertible": "qty"},
		{"label": _("In Value"), "fieldname": "in_val", "fieldtype": "Float", "width": 80},
		{"label": _("Out Qty"), "fieldname": "out_qty", "fieldtype": "Float", "width": 80, "convertible": "qty"},
		{"label": _("Out Value"), "fieldname": "out_val", "fieldtype": "Float", "width": 80},
		{"label": _("Balance Qty"), "fieldname": "bal_qty", "fieldtype": "Float", "width": 100, "convertible": "qty"},
		{"label": _("Balance Value"), "fieldname": "bal_val", "fieldtype": "Currency", "width": 100},
		{"label": _("Valuation Rate"), "fieldname": "val_rate", "fieldtype": "Currency", "width": 90, "convertible": "rate"},
	]

	return columns

def get_conditions(filters):
	conditions = ""
	if not filters.get("from_date"):
		frappe.throw(_("'From Date' is required"))

	if filters.get("to_date"):
		conditions += " and posting_date <= %(to_date)s"
	else:
		frappe.throw(_("'To Date' is required"))

	if filters.get("batch_no"):
		conditions += " and batch_no = %(batch_no)s"

	if filters.get("warehouse"):
		conditions += " and warehouse = %(warehouse)s"

	return conditions

def get_item_conditions(filters):
	from erpnext.stock.report.stock_ledger.stock_ledger import get_item_group_condition
	conditions = []
	if filters.get("item_code"):
		conditions.append("item.name=%(item_code)s")
	else:
		if filters.get("brand"):
			conditions.append("item.brand=%(brand)s")
		if filters.get("item_group"):
			conditions.append(get_item_group_condition(filters.get("item_group")))

	items = []
	if conditions:
		items = frappe.db.sql_list("""select name from `tabItem` item where {}"""
			.format(" and ".join(conditions)), filters)
	item_conditions_sql = ''
	if items:
		item_conditions_sql = ' and sle.item_code in ({})' \
			.format(', '.join([frappe.db.escape(i) for i in items]))

	return item_conditions_sql

# get all details
def get_stock_ledger_entries(filters):
	item_conditions = get_item_conditions(filters)
	conditions = get_conditions(filters)

	return frappe.db.sql("""select item_code, batch_no, warehouse,
		posting_date, actual_qty, batch_valuation_rate, batch_qty_after_transaction, stock_value_difference
		from `tabStock Ledger Entry` sle
		where docstatus < 2 and ifnull(batch_no, '') != '' {0} {1} order by item_code, warehouse
		""".format(conditions, item_conditions), filters, as_dict=1)

def get_item_warehouse_batch_map(filters):
	sle = get_stock_ledger_entries(filters)
	iwb_map = {}

	from_date = getdate(filters["from_date"])
	to_date = getdate(filters["to_date"])

	db_qty_precision = 6 if cint(frappe.db.get_default("float_precision")) <= 6 else 9

	for d in sle:
		iwb_map.setdefault(d.item_code, {}).setdefault(d.warehouse, {})\
			.setdefault(d.batch_no, frappe._dict({
				"opening_qty": 0.0, "opening_val": 0.0,
				"in_qty": 0.0, "in_val": 0.0,
				"out_qty": 0.0, "out_val": 0.0,
				"bal_qty": 0.0, "bal_val": 0.0,
				"val_rate": 0.0
			}))
		qty_dict = iwb_map[d.item_code][d.warehouse][d.batch_no]

		if d.voucher_type == "Stock Reconciliation":
			qty_diff = flt(d.batch_qty_after_transaction) - flt(qty_dict.bal_qty)
		else:
			qty_diff = flt(d.actual_qty)

		value_diff = flt(d.stock_value_difference)

		if d.posting_date < from_date:
			qty_dict.opening_qty += qty_diff
			qty_dict.opening_val += value_diff

		elif d.posting_date >= from_date and d.posting_date <= to_date:
			if flt(qty_diff, db_qty_precision) >= 0:
				qty_dict.in_qty += qty_diff
				qty_dict.in_val += value_diff
			else:
				qty_dict.out_qty += abs(qty_diff)
				qty_dict.out_val += abs(value_diff)

		qty_dict.val_rate = d.batch_valuation_rate
		qty_dict.bal_qty += qty_diff
		qty_dict.bal_val += value_diff

	return iwb_map

def get_item_details(filters):
	item_map = {}
	for d in frappe.db.sql("select name, item_name, description, stock_uom from tabItem", as_dict=1):
		item_map.setdefault(d.name, d)

	return item_map
