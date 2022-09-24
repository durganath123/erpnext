frappe.provide('erpnext');

frappe.ui.form.on('User', {
	onload: function(frm) {
		if(has_access_to_edit_user() && frm.fields_dict.item_groups_allowed_html) {
			if(!frm.item_groups_editor) {
				frm.item_groups_editor = new erpnext.CustomerItemGroupEditor(frm, frm.fields_dict.item_groups_allowed_html.wrapper);
			}
		}
	},
	refresh: function (frm) {
		frm.item_groups_editor && frm.item_groups_editor.refresh();
	}
});

erpnext.CustomerItemGroupEditor = Class.extend({
	init: function(frm, wrapper) {
		this.wrapper = $('<div class="row customer-ig-list"></div>').appendTo(wrapper);
		this.frm = frm;
		this.make(frm);
	},
	make: function(frm) {
		var me = this;
		frappe.call({
			method: "erpnext.portal.doctype.products_settings.products_settings.get_item_groups_allowed",
			callback: function (r) {
				if (r.message) {
					r.message.forEach(function (item_group) {
						$(repl('<div class="col-sm-6"><div class="checkbox">\
					<label><input type="checkbox" class="customer-ig-check" data-item-group="%(item_group)s">\
					%(item_group)s</label></div></div>', {item_group: item_group})).appendTo(me.wrapper);
					});
					me.bind();
					me.refresh();
				}
			}
		});
	},
	refresh: function() {
		var me = this;
		this.wrapper.find(".customer-ig-check").prop("checked", false);
		$.each(this.frm.doc.item_groups_allowed, function(i, d) {
			me.wrapper.find(".customer-ig-check[data-item-group='"+ d.item_group +"']").prop("checked", true);
		});
	},
	bind: function() {
		var me = this;
		this.wrapper.on("change", ".customer-ig-check", function() {
			var item_group = $(this).attr('data-item-group');
			if($(this).prop("checked")) {
				me.frm.add_child("item_groups_allowed", {"item_group": item_group});
			} else {
				// remove from item_groups_allowed
				me.frm.doc.item_groups_allowed = $.map(me.frm.doc.item_groups_allowed || [], function(d) { if(d.item_group != item_group){ return d } });
			}
		});
	}
});