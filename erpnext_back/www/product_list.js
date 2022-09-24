frappe.provide('product');
var shopping_cart = erpnext.shopping_cart;

frappe.ready(function() {
    product.item_group = frappe.utils.get_url_arg("item_group");

    shopping_cart.cart_update_item_callbacks.push(product.handle_item_changed);
    shopping_cart.cart_update_doc_callbacks.push(product.handle_qoutation_changed);
    shopping_cart.cart_update_callbacks.push(product.handle_cart_changed);

    product.create_fields();
    product.bind_change_qty();
    product.bind_change_uom();
    product.bind_product_qty();
    window.zoom_item_image(".products-wrapper",".product-page-image", "data-item-image");
});

product.create_fields = function() {
    product.field_group = new frappe.ui.FieldGroup({
        parent: $('#product-field'),
        fields: [
            {
                label: __('Delivery Date'),
                fieldname: 'delivery_date',
                fieldtype: 'Date',
                reqd: 1,
                onchange: product.handle_delivery_date_changed
            },
        ]
    });
    product.field_group.make();

    let values = {};
    $(`.product-field-data`).each(function (i, e) {
        let $this = $(this);
        values[$this.data('fieldname')] = $this.text();
    });
    frappe.run_serially([
        () => shopping_cart.ignore_update = true,
        () => product.field_group.set_values(values),
        () => shopping_cart.ignore_update = false
    ]);
}

product.bind_change_qty = function() {
    $(".products-wrapper").on("change", ".product-qty", function() {
        var item_code = $(this).attr("data-item-code");
        var newVal = $(this).val();

        shopping_cart.update_cart_item({
            item_code: item_code,
            fieldname: 'qty',
            value: newVal
        });
    });
}

product.bind_change_uom = function() {
    $(".products-wrapper").on("change", ".product-uom", function() {
        var item_code = $(this).attr("data-item-code");
        var newVal = $(this).val();

        shopping_cart.update_cart_item({
            item_code: item_code,
            fieldname: 'uom',
            value: newVal
        });
    });
}

product.handle_delivery_date_changed = function() {
    var delivery_date = product.field_group.get_value('delivery_date') || "";
    shopping_cart.update_cart_field({
        fieldname: 'delivery_date',
        value: delivery_date,
    });
}

product.handle_item_changed = function(r, opts) {
    if (!opts || !opts.item_code || !$(`.product-items-row[data-item-code='${opts.item_code}']`).length) {
        return;
    }

    var uom;
    if (opts.fieldname == 'uom' && opts.value) {
        uom = opts.value;
    }
    product.get_item_row(opts.item_code, uom);
}

product.handle_qoutation_changed = function() {
    product.get_items_table();
}

product.handle_cart_changed = function(r) {
    frappe.run_serially([
        () => shopping_cart.ignore_update = true,
        () => product.field_group.set_values(r.message.quotation_fields || {}),
        () => shopping_cart.ignore_update = false
    ]);
}

product.get_item_row = function(item_code, uom) {
    return frappe.call({
        type: "POST",
        method: "erpnext.www.product_list.get_item_row",
        freeze: true,
        args: {
            item_code: item_code,
            uom: uom
        },
        callback: function(r) {
            if (r && r.message) {
                $(`.product-items-row[data-item-code="${item_code}"]`).replaceWith(r.message);
            }
        }
    });
};

product.get_items_table = function() {
    return frappe.call({
        method: "erpnext.www.product_list.get_items_table",
        freeze: true,
        args: {
            item_group: product.item_group
        },
        callback: function(r) {
            if (r) {
                $(".products-wrapper").html(r.message);
            }
        }
    });
}

product.bind_product_qty = function() {
    $(".products-wrapper").on("focus", ".product-qty", function() {
        $(this).select();
    });

    $(".products-wrapper").on('keydown', "input.product-qty", function(e) {
        window.handle_up_down_arrow_key(e, this, "input.product-qty");
    });
}
