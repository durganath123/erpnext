# -*- coding: utf-8 -*-
# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, cstr
from frappe.model.document import Document
from erpnext.selling.report.qty_adjust.qty_adjust import get_data

class QtyAdjustStockCount(Document):
	def validate(self):
		self.calculate_totals()

	def on_update(self):
		frappe.cache().hdel('qty_adjust_stock_count', self.name)

	def onload(self):
		local_doc = frappe.cache().hget('qty_adjust_stock_count', self.name)
		if local_doc is not None:
			self.update(local_doc)
			self.set_onload('has_local_changes', 1)
		else:
			self.set_onload('has_local_changes', 0)

	def get_item_input_map(self):
		out = {}
		for d in self.items:
			if d.item_code:
				out[d.item_code] = frappe._dict({
					'phyiscal_stock': flt(d.physical_stock),
					'ppk': flt(d.ppk),
				})

		return out

	def apply_item_input_map(self, input_map):
		for d in self.items:
			if d.item_code and d.item_code in input_map:
				d.update(input_map[d.item_code])

	def get_items(self):
		if not self.from_date or not self.to_date:
			frappe.throw(_("From Date and To Date are mandatory"))

		filters = frappe._dict({
			'date': self.from_date,
			'selected_to_date': self.to_date,
			'item_group': self.item_group,
			'brand': self.brand,
		})

		input_map = self.get_item_input_map()
		self.items = []

		data = get_data(filters)
		for d in data:
			self.append('items', d)

		self.apply_item_input_map(input_map)
		self.calculate_totals()

		sorter = None
		if self.sort_by == "Item Code":
			sorter = lambda d: cstr(d.item_code)
		elif self.sort_by == "Item Name":
			sorter = lambda d: cstr(d.item_name)
		elif self.sort_by == "Net +/-":
			sorter = lambda d: flt(d.net_short_excess)
		elif self.sort_by == "Short(-)/Excess":
			sorter = lambda d: flt(d.short_excess)

		if sorter:
			self.items = sorted(self.items, key=sorter)
			for i, d in enumerate(self.items):
				d.idx = i + 1

	def calculate_totals(self):
		for d in self.items:
			d.net_short_excess = flt(d.physical_stock) + flt(d.total_selected_po_qty) - flt(d.total_selected_so_qty) - flt(d.ppk)

		self.total_actual_qty = sum([flt(d.actual_qty) for d in self.items])
		self.total_po_qty = sum([flt(d.total_selected_po_qty) for d in self.items])
		self.total_available_qty = sum([flt(d.total_available_qty) for d in self.items])
		self.total_so_qty = sum([flt(d.total_selected_so_qty) for d in self.items])
		self.total_short_excess = sum([flt(d.short_excess) for d in self.items])
		self.total_physical_stock = sum([flt(d.physical_stock) for d in self.items])
		self.total_ppk = sum([flt(d.ppk) for d in self.items])
		self.total_net_short_excess = sum([flt(d.net_short_excess) for d in self.items])


@frappe.whitelist()
def handle_change(name, fieldname, value, item_code=None):
	local_doc = frappe.cache().hget('qty_adjust_stock_count', name)
	if local_doc is None:
		local_doc = frappe.get_doc("Qty Adjust Stock Count", name)
	else:
		local_doc = frappe.get_doc(local_doc)

	if local_doc.docstatus != 0:
		return

	if item_code:
		to_modify = local_doc.get('items', {'item_code': item_code})
		to_modify = to_modify[0] if to_modify else None
	else:
		to_modify = local_doc

	if to_modify:
		to_modify.set(fieldname, value)

	local_doc.calculate_totals()
	publish_change(local_doc)


def publish_change(local_doc):
	if local_doc.is_new() or local_doc.docstatus != 0:
		return

	local_doc_dict = local_doc.as_dict()

	frappe.cache().hset('qty_adjust_stock_count', local_doc.name, local_doc_dict)

	frappe.publish_realtime('qty_adjust_stock_count_updated', local_doc_dict,
		doctype="Qty Adjust Stock Count", docname=local_doc.name)
