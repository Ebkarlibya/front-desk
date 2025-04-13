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
            this.wrapper.append(`
                <section class="customer-cart-container" 
                    style="
                        background: #fff; 
                        border-radius: 8px; 
                        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
                        padding: 1rem; 
                        margin-bottom: 1rem;
                    ">
                </section>
            `);
            this.$component = this.wrapper.find('.customer-cart-container');
        }
        init_child_components() {
            this.init_customer_selector();
            this.init_table_selector();
            this.init_cart_components();
        }

        init_table_selector() {
            this.$component.append(`
                <div class="table-section cart-section" 
                     style="
                         margin-bottom: 1rem; 
                         background: #f8f9fa;
                         border-radius: 6px;
                         padding: 0.8rem;
                         display: flex;
                         align-items: center;
                         gap: 0.5rem;
                     ">
                </div>
            `);
            this.$table_section = this.$component.find('.table-section');
            this.make_table_selector();
        }

        update_table_section() {
            const me = this;
            if (me.table_number) {
                this.$table_section.html(`
                    <div class="table-display selected" 
                         style="
                             display: flex; 
                             align-items: center; 
                             background: #e9ecef;
                             border-radius: 6px;
                             padding: 0.5rem 0.75rem; 
                             width: 100%;
                             justify-content: space-between;
                         ">
                        <div class="table-label" 
                             style="
                                 font-weight: 500; 
                                 font-size: 14px;
                                 color: #212529;
                             ">
                            ${__('Table')}: 
                            <span style="font-weight: bold; font-size: 14px; margin-right: 0.25rem;">
                                ${me.table_number}
                            </span>
                        </div>
                        <div class="reset-table-btn" 
                             title="${__('Change Table')}" 
                             style="
                                 cursor: pointer; 
                                 padding: 0.3rem 0.5rem;
                                 background: #fff;
                                 border-radius: 4px;
                                 transition: background 0.2s;
                             ">
                            <svg width="24" height="24" viewBox="0 0 14 14" fill="none">
                                <path d="M4.93764 4.93759L7.00003 6.99998M9.06243 9.06238L7.00003 6.99998M7.00003 6.99998L4.93764 9.06238L9.06243 4.93759" 
                                      stroke="#8D99A6" stroke-width="1.5"/>
                            </svg>
                        </div>
                    </div>
                `);
            } else {
                this.make_table_selector();
            }
        }


        make_table_selector() {
            this.$table_section.html(`
                <div class="table-field" style="width: 100%;">
                    <label style="
                        display: block; 
                        font-weight: 600; 
                        font-size: 14px; 
                        margin-bottom: 0.3rem;
                    ">
                        ${__('Select Table')}
                    </label>
                </div>
            `);
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
            this.table_field.toggle_label(false);
        }

        load_invoice() {
            super.load_invoice();
            const frm = this.events.get_frm();
            if (!frm || !frm.doc) return;
            const me = this;
            let loaded_table_number = null;


            frappe.call({
                method: "inn.inn_hotels.page.pos_extended.pos_extended.get_table_number",
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
                this.$component.append(`
                    <div class="cart-totals-section cart-section" 
                         style="
                             margin-top: 1rem; 
                             background: #fff; 
                             padding: 1rem; 
                             border-radius: 6px; 
                             box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                         ">
                    </div>
                `);
                this.$totals_section = this.$component.find('.cart-totals-section');
            } else {
                this.$totals_section.addClass('cart-section');
            }
            this.$totals_section.html(`
                <div class="add-discount-wrapper" 
                     style="
                         margin-bottom: 1rem; 
                         cursor: pointer; 
                         color: #495057; 
                         display: flex; 
                         align-items: center;
                     ">
                    ${this.get_discount_icon()} 
                    <span style="margin-left: 0.5rem; font-size: 14px; font-weight: 500;">
                        ${__('Add Discount')}
                    </span>
                </div>
                
                <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                    <div class="item-qty-total-container totals-line" 
                         style="
                             background: #f8f9fa; 
                             padding: 0.75rem; 
                             border-radius: 4px;
                             display: flex;
                             justify-content: space-between;
                             align-items: center;
                         ">
                        <div class="item-qty-total-label" style="font-size: 14px; color: #212529;">
                            ${__('Total Quantity')}
                        </div>
                        <div class="item-qty-total-value value" 
                             style="
                                 font-size: 15px; 
                                 font-weight: 600; 
                                 color: #212529;
                             ">
                            0
                        </div>
                    </div>
                    
                    <div class="net-total-container totals-line" 
                         style="
                             background: #f8f9fa; 
                             padding: 0.75rem; 
                             border-radius: 4px;
                             display: flex;
                             justify-content: space-between;
                             align-items: center;
                         ">
                        <div class="net-total-label" style="font-size: 14px; color: #212529;">
                            ${__("Net Total")}
                        </div>
                        <div class="net-total-value value" 
                             style="
                                 font-size: 15px; 
                                 font-weight: 600; 
                                 color: #212529;
                             ">
                            0.00
                        </div>
                    </div>

                    <div class="grand-total-container totals-line" 
                         style="
                             background: #e9ecef; 
                             padding: 0.8rem; 
                             border-radius: 4px;
                             display: flex;
                             justify-content: space-between;
                             align-items: center;
                         ">
                        <div style="font-size: 15px; font-weight: 600; color: #212529;">
                            ${__('Grand Total')}
                        </div>
                        <div class="grand-total-value value" 
                             style="
                                 font-size: 15px; 
                                 font-weight: 600; 
                                 color: #212529;
                             ">
                            0.00
                        </div>
                    </div>
                </div>

                <!-- قسم الأزرار المخصصة -->
                <div style="display: flex; flex-direction: column; gap: 0.75rem; margin-top: 1rem;">
                    <div class="print-order-section" 
                         style="
                             display: grid; 
                             grid-template-columns: 1fr 1fr; 
                             gap: 0.75rem;
                         ">
                        <button class="btn btn-secondary caption-order-btn" data-button-value="captain-order" 
                                disabled
                                style="
                                    padding: 0.6rem; 
                                    border-radius: 4px; 
                                    font-size: 14px;
                                    background-color:black;
                                    color:white;
                                    border: 1px solid white;
                                    border-radius: 10px;
                                ">
                            ${__('Captain Order')}
                        </button>
                        <button class="btn btn-secondary table-order-btn" data-button-value="table-order" 
                                disabled
                                style="
                                    padding: 0.6rem; 
                                    border-radius: 4px; 
                                    font-size: 14px;
                                    background-color:black;
                                    color:white;
                                    border: 1px solid white;
                                    border-radius: 10px;
                                ">
                            ${__('Table Order')}
                        </button>
                    </div>
                    
                    <button class="btn btn-secondary transfer-btn btn-block" 
                            disabled
                            style="
                                width: 100%; 
                                padding: 0.6rem; 
                                border-radius: 4px; 
                                font-size: 14px;
                                background-color:black;
                                color:white;
                                border: 1px solid white;
                                border-radius: 10px;
                            ">
                        ${__('Transfer Charges')}
                    </button>
                </div>

                <!-- أزرار الدفع/التعديل -->
                <div class="checkout-edit-section" 
                     style="
                         margin-top: 1rem; 
                         display: flex; 
                         flex-direction: column; 
                         gap: 0.75rem;
                     ">
                    <button class="btn btn-primary checkout-btn btn-block" 
                            disabled
                            style="
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                padding: 0.75rem; 
                                font-size: 15px; 
                                border-radius: 10px;
                                background-color: #0d6efd;
                                border: none;
                                font-weight: 500;
                                color: #fff;
                            ">
                        ${__('Checkout')}
                    </button>
                    <button class="btn btn-secondary edit-cart-btn btn-block" 
                            style="
                                display: none; 
                                padding: 0.75rem; 
                                font-size: 15px; 
                                border-radius: 4px;
                                background-color: #f8f9fa;
                                border: 1px solid #ced4da;
                                color: #343a40;
                            ">
                        ${__('Edit Cart')}
                    </button>
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
            super.highlight_checkout_btn(toggle);
            this.$caption_order_btn?.prop('disabled', !toggle);
            this.$table_order_btn?.prop('disabled', !toggle);
            this.$transfer_btn?.prop('disabled', !toggle);
        }
        reset_table_section() {
            this.table_number = null;
            this.make_table_selector();
            this.events.table_selected?.(null);
        }

        bind_events() {
            super.bind_events();
            const me = this;
            this.$component.on("click", ".caption-order-btn", function () {
                if ($(this).prop('disabled')) return;
                me.events.print_captain_order?.();
            });
            this.$component.on("click", ".table-order-btn", function () {
                if ($(this).prop('disabled')) return;
                me.events.print_table_order?.();
            });
            this.$component.on("click", ".transfer-btn", function () {
                if ($(this).prop('disabled')) return;
                const frm = me.events.get_frm();
                if (!frm || !frm.doc) return;
                const currentGrandTotalValue = frm.doc.grand_total;
                if (!(currentGrandTotalValue > 0)) {
                    frappe.show_alert({ 
                        message: __("Cannot transfer zero or negative amount."), 
                        indicator: "orange" 
                    });
                    return;
                }
                me.events.transfer_folio?.(currentGrandTotalValue);
            });
            this.$component.on("click", ".reset-table-btn", function () {
                me.reset_table_section();
            });
        }
    }
})

export default inn.PointOfSale.PosExtendItemCart