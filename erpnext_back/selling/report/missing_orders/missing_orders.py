# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cint, getdate
from frappe import _


def execute(filters=None):
	if not filters: filters ={}
	doctype = filters.get("doctype")
	reference_delivery_date = getdate(filters.get('delivery_date'))
	enable_disable = filters.get('enable_disable')

	columns = get_columns(doctype)
	customers = get_sales_details(doctype, reference_delivery_date, enable_disable)

	for d in customers:
		d.update(get_last_sales_amt(d.customer, doctype))
	
	return columns, customers


def get_sales_details(doctype, reference_delivery_date, enable_disable):
	customer_condition = ''
	if enable_disable == 'Enabled Customers':
		customer_condition = 'and disabled = 0'
	elif enable_disable == 'Disabled Customers':
		customer_condition = 'and disabled = 1'

	fields = """sum(so.base_net_total) as 'total_order_considered',
			max(so.delivery_date) as 'last_delivery_date',
			DATEDIFF(CURDATE(), max(so.delivery_date)) as 'days_since_last_order' """
	if doctype == "Sales Order":
		fields = """sum(if(so.status = "Closed",
				so.base_net_total * so.per_delivered/100,
				so.base_net_total)) as 'total_order_considered',
			max(so.delivery_date) as 'last_delivery_date',
			DATEDIFF(CURDATE(), max(so.delivery_date)) as 'days_since_last_order'"""

	return frappe.db.sql("""select
			cust.name as customer,
			cust.customer_name,
			cust.territory,
			cust.customer_group,
			count(distinct(so.name)) as 'num_of_order',
			sum(base_net_total) as 'total_order_value', {0}
		from `tabCustomer` cust, `tab{1}` so
		where cust.name = so.customer and so.docstatus < 2 {2}
		group by cust.name
		having last_delivery_date < %s
		order by last_delivery_date desc
	""".format(fields, doctype, customer_condition), reference_delivery_date, as_dict=1)


def get_last_sales_amt(customer, doctype):
	cond = "delivery_date"
	res = frappe.db.sql("""
		select name as last_order, base_net_total as last_order_amount
		from `tab{0}`
		where customer = %s and docstatus < 2 order by {1} desc
		limit 1
	""".format(doctype, cond), customer, as_dict=1)

	return res and res[0] or {}


def get_columns(doctype):
	return [
		{"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Customer", "width": 240},
		{"fieldname": "last_delivery_date", "label": _("Last Delivery Date"), "fieldtype": "Date", "width": 130},
		{"fieldname": "days_since_last_order", "label": _("Day Since Last Delivery"), "fieldtype": "Int", "width": 100},
		{"fieldname": "last_order", "label": _("Last Order"), "fieldtype": "Link", "options": doctype, "width": 100},
		{"fieldname": "last_order_amount", "label": _("Last Order Amount"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "num_of_order", "label": _("Number Of Orders"), "fieldtype": "Int", "width": 125},
		{"fieldname": "total_order_considered", "label": _("Total Order Considered"), "fieldtype": "Currency", "width": 155},
		{"fieldname": "total_order_value", "label": _("Total Order Value"), "fieldtype": "Currency", "width": 122},
		{"fieldname": "customer_group", "label": _("Customer Group"), "fieldtype": "Link", "options": "Customer Group", "width": 120},
		{"fieldname": "territory", "label": _("Territory"), "fieldtype": "Link", "options": "Territory", "width": 120}
	]
