from __future__ import unicode_literals
import frappe

from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import getdate, validate_email_add, today, add_years,add_days,format_datetime
from datetime import datetime
from frappe.model.naming import make_autoname
from frappe import throw, _, scrub
import frappe.permissions
from frappe.model.document import Document
from frappe.utils import flt, cint
import json
import collections
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from erpnext.stock.utils import get_stock_balance
from operator import itemgetter 

@frappe.whitelist()
def addMaterialIssue(obj,doc_name):
	#obj=''
	res_obj=[]
	res_obj1=[]
	res_obj2=[]
	for row in json.loads(obj):
		obj1={}
		obj2={}
		if 'adj_quantity' in row:
			if not flt(row["adj_quantity"])==0.0:
				if not flt(row["current_qty"])<flt(row["qty"]):	
					result=multiBatchSet(row["item_code"],"Sundine Kestrel- . - .",row["adj_quantity"],True)
					for row_res in result:
						res_obj.append(row_res)

			if not flt(row["adj_quantity"])==0.0:
				if flt(row["current_qty"])<flt(row["qty"]):
					obj1["item_code"]=row["item_code"]
					obj1["batch_no"]=row["batch_no"]
					obj1["qty"]=flt(row["qty"])-flt(row["current_qty"])
					obj1["expense_account"]="5250 - Inventory Adjustment - ."
					res_obj2.append(obj1)

		if flt(row["current_qty"])==0.0:
			if not 'adj_quantity' in row:
				obj2["item_code"]=row["item_code"]
				obj2["qty"]=row["qty"]
				obj2["batch_no"]=row["batch_no"]
				#rate=getValuationRate(row["item_code"])
				#if not rate:
				#	frappe.throw(_("No Valuation Rate Available In System For Item {0}.").format(row["item_code"]))
				res_obj1.append(obj2)
		
	#return res_obj	
	if not len(res_obj)==0:	
		addStockEntry(res_obj,doc_name)
	if not len(res_obj1)==0:
		addStockEntry1(res_obj1,doc_name)
	if not len(res_obj2)==0:
		addStockEntry1(res_obj2,doc_name)
	#return res_obj


@frappe.whitelist()
def addStockEntry(item,name):
	doc=frappe.get_doc({
				"docstatus": 0,
				"doctype": "Stock Entry",
				"name": "New Stock Entry 2",
				"naming_series": "STE-",
				"purpose": "Material Issue",
				"custom_purpose":"Qty Adjusted",	
				"company": "Sundine Produce",
				"items":item,
				"from_warehouse": "Sundine Kestrel- . - .",
				"stock_reconsilation":str(name)
			})
	res=doc.insert()
	res.submit()
	return res

@frappe.whitelist()
def addStockEntry1(item,name):
	doc1=frappe.get_doc({
				"docstatus": 0,
				"doctype": "Stock Entry",
				"name": "New Stock Entry 2",
				"naming_series": "STE-",
				"purpose": "Material Receipt",
				"custom_purpose":"Qty Adjusted",
				"company": "Sundine Produce",
				"items":item,
				"to_warehouse": "Sundine Kestrel- . - .",
				"stock_reconsilation":str(name)
			})
	res1=doc1.insert()
	res1.submit()


@frappe.whitelist()
def getValuationRate(item_code):
	last_valuation_rate = frappe.db.sql("""select valuation_rate
		from `tabStock Ledger Entry`
		where item_code = %s and warehouse ='Sundine Kestrel- . - .'
		and valuation_rate >= 0
		order by posting_date desc, posting_time desc, name desc limit 1""",item_code)
	return last_valuation_rate


	

	
	



@frappe.whitelist()
def multiBatchSet(item_code,warehouse,qty,throw=False):
	#doc=frappe.get_doc("Sales Invoice",name)
	#itemdoc=frappe.get_doc("Sales Invoice Item",doc_name)
	batches = get_batches(item_code, warehouse, qty, throw)
	set_batch=False
	response_batch=[]
	#for batch in batches:
	#	res_batch={}
	#	if cint(qty) <= cint(batch.qty):
	#		res_batch["item_code"]=item_code
	#		res_batch["qty"]=qty
	#		res_batch["batch_no"]=batch.batch_id
	#		res_batch["expense_account"]="5250 - Inventory Adjustment - ."
	#		set_batch=True
	#		response_batch.append(res_batch)
	#frappe.msgprint(json.dumps(response_batch))
	#return response_batch

	if set_batch==False:
		total=0
		for batch in batches:
			total=float(total)+float(batch.qty)

		if float(total)<float(qty):
			#frappe.throw("Insufficient All Batch Qty To Fullfill Order Quantity")
			frappe.throw(_("Insufficient Batch Qty For Item {0} and quantity is {1} and available quantity in All batchs is {2}").format(item_code,qty,total))

		rem_qty=float(qty)
		count=0
		for batch2 in batches:

			if float(batch2.qty)>0:
				if not float(rem_qty)==0:
					res_batch={}
					if float(batch2.qty)<=float(rem_qty):
						if count==0:
							#itemAddUpdate(doc_name,batch2.batch_id,batch2.qty,True)
							res_batch["item_code"]=item_code
							res_batch["qty"]=batch2.qty
							res_batch["batch_no"]=batch2.batch_id
							res_batch["expense_account"]="5250 - Inventory Adjustment - ."
							rem_qty=rem_qty-batch2.qty
							count=count+1
							response_batch.append(res_batch)
							#doc.insert()
							#doc1=frappe.get_doc("Sales Invoice Item")
						else:
							res_batch["item_code"]=item_code
							res_batch["qty"]=batch2.qty
							res_batch["batch_no"]=batch2.batch_id
							res_batch["expense_account"]="5250 - Inventory Adjustment - ."
							response_batch.append(res_batch)
							#itemAddUpdate(doc_name,batch2.batch_id,batch2.qty)
							rem_qty=rem_qty-batch2.qty

					else:
						if count==0:
							res_batch["item_code"]=item_code
							res_batch["qty"]=rem_qty
							res_batch["batch_no"]=batch2.batch_id
							res_batch["expense_account"]="5250 - Inventory Adjustment - ."
							rem_qty=rem_qty-batch2.qty
							response_batch.append(res_batch)

						else:
							
							res_batch["item_code"]=item_code
							res_batch["qty"]=rem_qty
							res_batch["batch_no"]=batch2.batch_id
							res_batch["expense_account"]="5250 - Inventory Adjustment - ."
							response_batch.append(res_batch)
						#itemAddUpdate(doc_name,batch2.batch_id,rem_qty)
						break
		return response_batch
	
	#time.sleep(5)
	#doc_final=frappe.get_doc("Sales Invoice",name)
	#doc_final.save()
	#frappe.db.commit()

		


def get_batches(item_code, warehouse, qty=1, throw=False):
	batches = frappe.db.sql(
		'select batch_id, sum(actual_qty) as qty from `tabBatch` join `tabStock Ledger Entry` '
		'on `tabBatch`.batch_id = `tabStock Ledger Entry`.batch_no '
		'where `tabStock Ledger Entry`.item_code = %s and  `tabStock Ledger Entry`.warehouse = %s '
		'and (`tabBatch`.expiry_date >= CURDATE() or `tabBatch`.expiry_date IS NULL)'
		'group by batch_id '
		'order by `tabBatch`.expiry_date ASC, `tabBatch`.creation ASC',
		(item_code, warehouse),
		as_dict=True
	)

	return batches
			
@frappe.whitelist()
def get_items(warehouse, posting_date, posting_time, company,item_code=None,enbl_dsbl=None,item_group=None):
	if item_code:
		items = frappe.get_list("Bin", fields=["item_code"], filters={"warehouse": warehouse,"item_code":item_code}, as_list=1)

		items += frappe.get_list("Item", fields=["name"], filters= {"is_stock_item": 1,"has_variants": 0,"default_warehouse": warehouse,"item_code":item_code},
				as_list=1)
	else:
		items = frappe.get_list("Bin", fields=["item_code"], filters={"warehouse": warehouse}, as_list=1)

		items += frappe.get_list("Item", fields=["name"], filters= {"is_stock_item": 1, "has_variants": 0, "default_warehouse": warehouse,"disabled":0},
				as_list=1)
		

	res = []
	for item in sorted(set(items)):
		stock_bal = get_stock_balance(item[0], warehouse, posting_date, posting_time,
			with_valuation_rate=True)
		if frappe.db.get_value("Item",item[0],"is_sales_item") == 1:
			if item_group:
				if frappe.db.get_value("Item",item[0],"item_group") == str(item_group):
					if item_code:
						if frappe.db.get_value("Item",item[0],"name") == str(item_code):
							if enbl_dsbl:
								if enbl_dsbl=="Enabled":
									if frappe.db.get_value("Item",item[0],"disabled") == 0:
										res.append({
											"item_code": item[0],
											"batch_no": item[0],
											"warehouse": warehouse,
											"qty": stock_bal[0],
											"item_name": frappe.db.get_value('Item', item[0], 'item_name'),
											"valuation_rate": stock_bal[1],
											"current_qty": stock_bal[0],
											"current_valuation_rate": stock_bal[1],
											"cost_center":getCostCenter(item[0],company)
										})
								else:
									if frappe.db.get_value("Item",item[0],"disabled") == 1:
										res.append({
												"item_code": item[0],
												"batch_no": item[0],
												"warehouse": warehouse,
												"qty": stock_bal[0],
												"item_name": frappe.db.get_value('Item', item[0], 'item_name'),
												"valuation_rate": stock_bal[1],
												"current_qty": stock_bal[0],
												"current_valuation_rate": stock_bal[1],
												"cost_center":getCostCenter(item[0],company)
										})
							else:
								#if frappe.db.get_value("Item",item[0],"disabled") == 0:
								res.append({
											"item_code": item[0],
											"batch_no": item[0],
											"warehouse": warehouse,
											"qty": stock_bal[0],
											"item_name": frappe.db.get_value('Item', item[0], 'item_name'),
											"valuation_rate": stock_bal[1],
											"current_qty": stock_bal[0],
											"current_valuation_rate": stock_bal[1],
											"cost_center":getCostCenter(item[0],company)
								})
					
									
					else:
						if enbl_dsbl:
							if enbl_dsbl=="Enabled":
								if frappe.db.get_value("Item",item[0],"disabled") == 0:
									res.append({
										"item_code": item[0],
										"batch_no": item[0],
										"warehouse": warehouse,
										"qty": stock_bal[0],
										"item_name": frappe.db.get_value('Item', item[0], 'item_name'),
										"valuation_rate": stock_bal[1],
										"current_qty": stock_bal[0],
										"current_valuation_rate": stock_bal[1],
										"cost_center":getCostCenter(item[0],company)
									})
							else:
								if frappe.db.get_value("Item",item[0],"disabled") == 1:
									res.append({
											"item_code": item[0],
											"batch_no": item[0],
											"warehouse": warehouse,
											"qty": stock_bal[0],
											"item_name": frappe.db.get_value('Item', item[0], 'item_name'),
											"valuation_rate": stock_bal[1],
											"current_qty": stock_bal[0],
											"current_valuation_rate": stock_bal[1],
											"cost_center":getCostCenter(item[0],company)
									})
						else:
							#frappe.msgprint("Item Group")
							#if frappe.db.get_value("Item",item[0],"disabled") == 0:
							res.append({
										"item_code": item[0],
										"batch_no": item[0],
										"warehouse": warehouse,
										"qty": stock_bal[0],
										"item_name": frappe.db.get_value('Item', item[0], 'item_name'),
										"valuation_rate": stock_bal[1],
										"current_qty": stock_bal[0],
										"current_valuation_rate": stock_bal[1],
										"cost_center":getCostCenter(item[0],company)
							})

			else:
				if item_code:
					if frappe.db.get_value("Item",item[0],"item_code") ==item_code:
						if enbl_dsbl:
							if enbl_dsbl=="Enabled":
								if frappe.db.get_value("Item",item[0],"disabled") == 0:
									res.append({
										"item_code": item[0],
										"batch_no": item[0],
										"warehouse": warehouse,
										"qty": stock_bal[0],
										"item_name": frappe.db.get_value('Item', item[0], 'item_name'),
										"valuation_rate": stock_bal[1],
										"current_qty": stock_bal[0],
										"current_valuation_rate": stock_bal[1],
										"cost_center":getCostCenter(item[0],company)
									})
							else:
								if frappe.db.get_value("Item",item[0],"disabled") == 1:
									res.append({
											"item_code": item[0],
											"batch_no": item[0],
											"warehouse": warehouse,
											"qty": stock_bal[0],
											"item_name": frappe.db.get_value('Item', item[0], 'item_name'),
											"valuation_rate": stock_bal[1],
											"current_qty": stock_bal[0],
											"current_valuation_rate": stock_bal[1],
											"cost_center":getCostCenter(item[0],company)
									})
						else:
							#if frappe.db.get_value("Item",item[0],"disabled") == 0:
							res.append({
									"item_code": item[0],
									"batch_no": item[0],
									"warehouse": warehouse,
									"qty": stock_bal[0],
									"item_name": frappe.db.get_value('Item', item[0], 'item_name'),
									"valuation_rate": stock_bal[1],
									"current_qty": stock_bal[0],
									"current_valuation_rate": stock_bal[1],
									"cost_center":getCostCenter(item[0],company)
								})
													
					else:
						if enbl_dsbl:
							if enbl_dsbl=="Enabled":
								if frappe.db.get_value("Item",item[0],"disabled") == 0:
									res.append({
										"item_code": item[0],
										"batch_no": item[0],
										"warehouse": warehouse,
										"qty": stock_bal[0],
										"item_name": frappe.db.get_value('Item', item[0], 'item_name'),
										"valuation_rate": stock_bal[1],
										"current_qty": stock_bal[0],
										"current_valuation_rate": stock_bal[1],
										"cost_center":getCostCenter(item[0],company)
									})
							else:
								if frappe.db.get_value("Item",item[0],"disabled") == 1:
									res.append({
											"item_code": item[0],
											"batch_no": item[0],
											"warehouse": warehouse,
											"qty": stock_bal[0],
											"item_name": frappe.db.get_value('Item', item[0], 'item_name'),
											"valuation_rate": stock_bal[1],
											"current_qty": stock_bal[0],
											"current_valuation_rate": stock_bal[1],
											"cost_center":getCostCenter(item[0],company)
									})
						else:
							#frappe.msgprint("Item Group")
							#if frappe.db.get_value("Item",item[0],"disabled") == 0:
							res.append({
									"item_code": item[0],
									"batch_no": item[0],
									"warehouse": warehouse,
									"qty": stock_bal[0],
									"item_name": frappe.db.get_value('Item', item[0], 'item_name'),
									"valuation_rate": stock_bal[1],
									"current_qty": stock_bal[0],
									"current_valuation_rate": stock_bal[1],
									"cost_center":getCostCenter(item[0],company)
							})

				else:
					if enbl_dsbl:
						if enbl_dsbl=="Enabled":
							if frappe.db.get_value("Item",item[0],"disabled") == 0:
								res.append({
										"item_code": item[0],
										"batch_no": item[0],
										"warehouse": warehouse,
										"qty": stock_bal[0],
										"item_name": frappe.db.get_value('Item', item[0], 'item_name'),
										"valuation_rate": stock_bal[1],
										"current_qty": stock_bal[0],
										"current_valuation_rate": stock_bal[1],
										"cost_center":getCostCenter(item[0],company)
									})
							else:
								if frappe.db.get_value("Item",item[0],"disabled") == 1:
									res.append({
											"item_code": item[0],
											"batch_no": item[0],
											"warehouse": warehouse,
											"qty": stock_bal[0],
											"item_name": frappe.db.get_value('Item', item[0], 'item_name'),
											"valuation_rate": stock_bal[1],
											"current_qty": stock_bal[0],
											"current_valuation_rate": stock_bal[1],
											"cost_center":getCostCenter(item[0],company)
									})
						else:
							if frappe.db.get_value("Item",item[0],"disabled") == 1:
								res.append({
										"item_code": item[0],
										"batch_no": item[0],
										"warehouse": warehouse,
										"qty": stock_bal[0],
										"item_name": frappe.db.get_value('Item', item[0], 'item_name'),
										"valuation_rate": stock_bal[1],
										"current_qty": stock_bal[0],
										"current_valuation_rate": stock_bal[1],
										"cost_center":getCostCenter(item[0],company)
								})
					else:
						res.append({
								"item_code": item[0],
								"batch_no": item[0],
								"warehouse": warehouse,
								"qty": stock_bal[0],
								"item_name": frappe.db.get_value('Item', item[0], 'item_name'),
								"valuation_rate": stock_bal[1],
								"current_qty": stock_bal[0],
								"current_valuation_rate": stock_bal[1],
								"cost_center":getCostCenter(item[0],company)
						})

	return sorted(res,key=itemgetter('item_code'),reverse = False)

@frappe.whitelist()
def getCostCenter(item,company):
	data=frappe.db.sql("""select buying_cost_center from `tabItem` where name=%s""",item)
	if data:
		if not data[0][0]==None:
			return data[0][0]
		else:
			return frappe.get_cached_value('Company',  company,  "cost_center")
	else:
		return frappe.get_cached_value('Company',  company,  "cost_center")
		
@frappe.whitelist()
def get_warehouse():
	return frappe.db.get_single_value('Stock Settings', 'default_warehouse')
