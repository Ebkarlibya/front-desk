frappe.require(["point-of-sale.bundle.js", "inn-pos.bundle.js"], function () {
    frappe.provide('inn.PointOfSale');
    inn.PointOfSale.PosExtendItemCart = class PosExtendItemCart extends erpnext.PointOfSale.ItemCart {
        constructor({ wrapper, events, settings }) {
            super({ wrapper, events, settings });
            this.table_number = null;
            this.table_field = null;
        }
        make() {
			super.make();
		}
        init_dom() {
            this.wrapper.append(
                `<section class="customer-cart-container"></section>`
            );
            this.$component = this.wrapper.find('.customer-cart-container');
        }
        init_child_components() {
            this.init_customer_selector();
            this.init_table_selector();
            this.init_cart_components();
        }

        init_table_selector() {
            this.$component.append(
                `<div class="table-section cart-section"></div>`
            );
            this.$table_section = this.$component.find('.table-section');
            this.make_table_selector();
        }

        update_table_section() {
            const me = this;
            if (me.table_number) {
                this.$table_section.html(`
                <div class="table-display selected" style="display: flex; align-items: center; padding: var(--padding-sm) 0;">
                    <div class="table-label" style="flex: 1; font-weight: 500;">
                        ${__('Table')}: <span style="font-weight: bold;">${me.table_number}</span>
                    </div>
                    <div class="reset-table-btn" title="${__('Change Table')}" style="cursor: pointer; padding: 0 var(--padding-xs);">
                        <svg width="24" height="24" viewBox="0 0 14 14" fill="none">
                            <path d="M4.93764 4.93759L7.00003 6.99998M9.06243 9.06238L7.00003 6.99998M7.00003 6.99998L4.93764 9.06238L9.06243 4.93759" stroke="#8D99A6" stroke-width="1.5"/>
                        </svg>
                    </div>
                </div>
                `);
            } else {
                this.make_table_selector();
            }
        }


        make_table_selector() {
            this.$table_section.html(`<div class="table-field" style="padding: var(--padding-sm) 0;"></div>`);
            const me = this;
            this.table_field = frappe.ui.form.make_control({
                df: {
                    label: __('Select Table'),
                    fieldtype: 'Link',
                    options: 'Inn Point Of Sale Table',
                    placeholder: __('Search and select table number'),
                    fieldname: 'pos_table_select',
                    get_query: function () {
                        return {
                            filters: [
                                ["Inn Point Of Sale Table", "status", "=", "Empty"]
                            ]
                        }
                    },
                    onchange: function () {
                        const selected_table = this.get_value();
                        if (selected_table) {
                            me.table_number = selected_table;
                            me.update_table_section();
                            me.events.table_selected?.(selected_table);
                        } else {
                            me.table_number = null;
                            me.update_table_section();
                            me.events.table_selected?.(null);
                        }
                    }
                },
                parent: this.$table_section.find('.table-field'),
                render_input: true,
            });
            this.table_field.toggle_label(true)
        }

        load_invoice() {
            super.load_invoice()

            const frm = this.events.get_frm()
            if (!frm || !frm.doc) return;
            const me = this;
            let loaded_table_number = null;


            frappe.call({
                method: "inn.inn_hotels.page.pos_extended.pos_extended.get_table_number", // Adjust method path
                args: {
                    invoice_name: frm.doc.name
                },
                callback: function (r) {
                    if (r.message && r.message.table) {
                        loaded_table_number = r.message.table;
                        me.table_number = loaded_table_number;
                    } else {
                        me.table_number = null;
                    }
                    me.update_table_section();
                },
                error: function(r) {
                    me.table_number = null;
                    me.update_table_section();
                }
            })
        }

        make_cart_totals_section() {
            this.$totals_section = this.$component.find('.cart-totals-section');

            if (this.$totals_section.length === 0) {
                 this.$component.append('<div class="cart-totals-section cart-section"></div>');
                 this.$totals_section = this.$component.find('.cart-totals-section');
            } else {
                 this.$totals_section.addClass('cart-section');
            }
            this.$totals_section.html(`
                <div class="add-discount-wrapper" style="margin-bottom: var(--margin-sm); cursor: pointer; color: var(--text-color); display: flex; align-items: center;">
                    ${this.get_discount_icon()} <span style="margin-left: var(--margin-xs);">${__('Add Discount')}</span>
                </div>
                <div class="item-qty-total-container totals-line">
                    <div class="item-qty-total-label">${__('Total Quantity')}</div>
                    <div class="item-qty-total-value value">0</div>
                </div>
                <div class="net-total-container totals-line">
                    <div class="net-total-label">${__("Net Total")}</div>
                    <div class="net-total-value value">0.00</div>
                </div>
                <div class="taxes-container">
                    <!-- Tax rows will be added dynamically by parent update_taxes -->
                </div>
                <div class="grand-total-container totals-line">
                    <div style="font-weight: bold;">${__('Grand Total')}</div>
                    <div class="grand-total-value value" style="font-weight: bold;">0.00</div>
                </div>

                <!-- Custom Buttons Section -->
                <div class="print-order-section" style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--margin-sm); margin-top: var(--margin-md);">
                    <button class="btn btn-secondary caption-order-btn" data-button-value="captain-order" disabled>${__('Captain Order')}</button>
                    <button class="btn btn-secondary table-order-btn" data-button-value="table-order" disabled>${__('Table Order')}</button>
                </div>
                <div class="transfer-btn-section" style="margin-top: var(--margin-sm);">
                     <button class="btn btn-secondary transfer-btn btn-block" disabled>${__('Transfer Charges')}</button>
                </div>

                <!-- Standard Buttons (Checkout/Edit Cart) -->
                <div class="checkout-edit-section" style="margin-top: var(--margin-md);">
                    <button class="btn btn-primary checkout-btn btn-block" disabled>${__('Checkout')}</button>
                    <button class="btn btn-secondary edit-cart-btn btn-block" style="display: none;">${__('Edit Cart')}</button>
                </div>
            `);

            this.$add_discount_elem = this.$component.find(".add-discount-wrapper");
            this.$item_qty_total = this.$component.find(".item-qty-total-value");
            this.$net_total = this.$component.find(".net-total-value");
            this.$grand_total = this.$component.find(".grand-total-value");
            this.$taxes_container = this.$component.find(".taxes-container");
            this.$checkout_btn = this.$component.find(".checkout-btn");
            this.$edit_cart_btn = this.$component.find(".edit-cart-btn");
            this.$caption_order_btn = this.$component.find(".caption-order-btn");
            this.$table_order_btn = this.$component.find(".table-order-btn");
            this.$transfer_btn = this.$component.find(".transfer-btn");
        }
        update_totals(doc) {
            super.update_totals(doc);
            const has_items = doc.items && doc.items.length > 0;
            this.$caption_order_btn?.prop('disabled', !has_items);
            this.$table_order_btn?.prop('disabled', !has_items);
            this.$transfer_btn?.prop('disabled', !has_items);
        }

        highlight_checkout_btn(toggle) {
            super.highlight_checkout_btn(toggle)
            this.$caption_order_btn?.prop('disabled', !toggle);
            this.$table_order_btn?.prop('disabled', !toggle);
            this.$transfer_btn?.prop('disabled', !toggle);
        }
        reset_table_section() {
            this.table_number = null;
            this.make_table_selector()
            this.events.table_selected?.(null);
        }

        bind_events() {
            super.bind_events()

            const me = this;
            this.$component.on("click", ".caption-order-btn", function () {
                if ($(this).prop('disabled')) return;

                me.events.print_captain_order?.(); 
            })

            this.$component.on("click", ".table-order-btn", function () {
                if ($(this).prop('disabled')) return;

                 me.events.print_table_order?.()
            });

            this.$component.on("click", ".transfer-btn", function () {
                if ($(this).prop('disabled')) {
                    return; 
                }
                const frm = me.events.get_frm();
                if (!frm || !frm.doc) {
                     frappe.show_alert({ message: __("Cannot perform transfer: Form not available."), indicator: "red" });
                     return;
                }
                const currentGrandTotalValue = frm.doc.grand_total;
                if (!(currentGrandTotalValue > 0)) {
                    frappe.show_alert({ message: __("Cannot transfer zero or negative amount."), indicator: "orange" });
                    return;
                }
               me.events.transfer_folio?.(currentGrandTotalValue); // Call event handler in controller
            })

           this.$component.on("click", ".reset-table-btn", function () {
                me.reset_table_section();
            })
        }
    }
})

export default inn.PointOfSale.PosExtendItemCart