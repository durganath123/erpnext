from __future__ import unicode_literals
from frappe import _

def get_data():
	return {
		'fieldname': 'reference_name',
		'non_standard_fieldnames': {
			'Salary Slip': 'journal_entry',
		},
		'transactions': [
			{
				'label': _('Referenced By'),
				'items': ['Journal Entry', 'Payment Entry']
			},
		]
	}
