frappe.require(["point-of-sale.bundle.js", "inn-pos.bundle.js"], function () {

    inn.PointOfSale.PosExtendedPastOrderList = class PosExtendedPastOrderList extends erpnext.PointOfSale.PastOrderList {
        constructor({ wrapper, events }) {
            super({ wrapper, events });
        }

        prepare_dom() {
            super.prepare_dom();
            this.add_styles();
        }

        add_styles() {
            if (this.styles_added) return;

            const style = `
                .past-order-list {
                }

                /* تنسيق كل صف فاتورة باستخدام Flexbox */
                .past-order-list .invoice-wrapper {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 12px 8px;
                    border-bottom: 1px solid var(--border-color);
                    cursor: pointer;
                }
                .past-order-list .invoice-wrapper:hover {
                    background-color: var(--control-bg-on-hover);
                }
                .past-order-list .invoice-wrapper:last-child {
                    border-bottom: none;
                }

                /* --- تنسيق الأقسام الثلاثة --- */

                /* 1. قسم الاسم والعميل (اليسار) */
                .past-order-list .invoice-name-date {
                    flex: 1;
                    min-width: 0;
                    padding-right: 10px;
                    display: flex;
                    flex-direction: column;
                }
                .past-order-list .invoice-name {
                    font-weight: 600;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    margin-bottom: 4px;
                }
                .past-order-list .customer-info {
                    color: var(--text-muted);
                    display: flex;
                    align-items: center;
                    font-size: 0.85rem;
                }
                 .past-order-list .customer-info svg {
                    margin-right: 5px;
                    flex-shrink: 0;
                 }
                 .past-order-list .customer-info span {
                     white-space: nowrap;
                     overflow: hidden;
                     text-overflow: ellipsis;
                 }

                /* 2. قسم الطاولة (الوسط) */
                .past-order-list .table {
                    flex-basis: 60px; 
                    flex-shrink: 0; 
                    text-align: center;
                    font-weight: 600;
                    padding: 0 10px;
                }

                /* 3. قسم الإجمالي والتاريخ (اليمين) */
                .past-order-list .invoice-total-status {
                    flex-basis: 120px; 
                    flex-shrink: 0;
                    display: flex;
                    flex-direction: column;
                    align-items: flex-end;
                }
                .past-order-list .invoice-total {
                    font-weight: 600;
                    margin-bottom: 4px;
                    white-space: nowrap;
                }
                .past-order-list .posting-datetime {
                    color: var(--text-muted);
                    font-size: 0.85rem;
                    white-space: nowrap;
                }
                .past-order-list .seperator { display: none !important; }
            `;
            frappe.dom.set_style(style);
            this.styles_added = true;
        }

        refresh_list() {
            if (!this.$component.is(':visible')) {
                return;
            }
            frappe.dom.freeze();
            if (this.events && this.events.reset_summary) {
                this.events.reset_summary();
            }
            const search_term = this.search_field ? this.search_field.get_value() : '';
            const status = this.status_field.get_value();

            this.$invoices_container.html("");

            frappe.call({
                method: "inn.inn_hotels.page.pos_extended.pos_extended.get_past_order_list_with_table",
                freeze: false,
                args: { search_term, status },
                callback: (response) => {
                    if (response.message && Array.isArray(response.message)) {
                        if (response.message.length > 0) {
                            response.message.forEach((invoice) => {
                                if (invoice && typeof invoice === 'object' && invoice.name) {
                                    const invoice_html = this.get_invoice_html(invoice);
                                    this.$invoices_container.append(invoice_html);
                                } else {
                                    console.warn("Received invalid invoice data:", invoice);
                                }
                            });
                        } else {
                             this.$invoices_container.html(`<div class="text-muted text-center p-4">${__("No matching orders found.")}</div>`);
                        }
                    } else {
                        this.$invoices_container.html(`<div class="text-muted text-center p-4">${__("No recent orders found.")}</div>`);
                        console.error("Invalid response received from get_past_order_list_with_table:", response);
                    }
                },
                error: (err) => {
                    console.error("Error fetching past orders:", err);
                     this.$invoices_container.html(`<div class="text-danger text-center p-4">${__("Error loading recent orders.")}</div>`);
                },
                always: () => {
                     frappe.dom.unfreeze();
                }
            });
        }

        get_invoice_html(invoice) {
            const posting_datetime = frappe.datetime.str_to_user(
                invoice.posting_date + " " + (invoice.posting_time || '')
            );

            const table_number_display = invoice.table_number ? invoice.table_number : '—';
            const customer_name = invoice.customer ? invoice.customer : __("Walk-in");
            const invoice_name = invoice.name;

            const grand_total_display = format_currency(invoice.grand_total, invoice.currency) || '0';

            return `
            <div class="invoice-wrapper" data-invoice-name="${escape(invoice.name)}">
                <div class="invoice-name-date">
                    <div class="invoice-name">${invoice_name}</div>
                    <div class="customer-info">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="black"> {/* تم تغيير fill وإزالة خصائص stroke */}
                            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                            <circle cx="12" cy="7" r="4"/>
                        </svg>
                        <span>${frappe.ellipsis(customer_name, 20)}</span>
                    </div>
                </div>

                <div class="table">
                     ${table_number_display} 
                </div>

                <div class="invoice-total-status">
                    <div class="invoice-total">${grand_total_display}</div>
                    <div class="posting-datetime">${posting_datetime}</div>
                </div>
            </div>
            `;
        }
        make_filter_section() {
            const me = this;
            this.search_field = frappe.ui.form.make_control({
                df: {
                    label: __("Search"),
                    fieldtype: "Data",
                    placeholder: __("Search by invoice id or customer name"),
                },
                parent: this.$component.find(".search-field"),
                render_input: true,
            });
            this.status_field = frappe.ui.form.make_control({
                df: {
                    label: __("Invoice Status"),
                    fieldtype: "Select",
                    options: `Draft\nPaid\nConsolidated\nReturn`,
                    placeholder: __("Filter by invoice status"),
                    onchange: function () {
                        if (me.$component.is(":visible")) me.refresh_list();
                    },
                },
                parent: this.$component.find(".status-field"),
                render_input: true,
            });
            this.status_field.toggle_label(false);
            this.status_field.set_value("Draft");
        }

    }

    $(function() {
        if (erpnext && erpnext.PointOfSale && erpnext.PointOfSale.PastOrderList) {
             console.log("Attempting to override PastOrderList with PosExtendedPastOrderList");
             erpnext.PointOfSale.PastOrderList = inn.PointOfSale.PosExtendedPastOrderList;
         } else {
             console.error("Could not find erpnext.PointOfSale.PastOrderList to override.");
         }
    });

});