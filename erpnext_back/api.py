from __future__ import unicode_literals
import frappe


@frappe.whitelist()
def paymentReferenceDate(row,reference_doctype,reference_name):
	result_list2=[]
	d={}
	d["row"]=row
	doc = frappe.get_doc(reference_doctype, reference_name)
	d["cheque_no"] = ""
	d["due_date"] = doc.get("due_date") or doc.get("posting_date")
	if reference_doctype == "Journal Entry":
		d["cheque_no"] = doc.cheque_no
		d["due_date"] = doc.posting_date
	elif reference_doctype == "Purchase Invoice":
		d["cheque_no"] = doc.bill_no
		d["due_date"] = doc.received_date
	elif reference_doctype == "Sales Invoice":
		d["due_date"] = doc.posting_date
	elif reference_doctype == "Landed Cost Voucher":
		d["cheque_no"] = doc.bill_no
		d["cheque_no"] = doc.bill_no
	
	result_list2.append(d)
	return result_list2
