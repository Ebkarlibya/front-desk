frappe.provide('erpnext.PointOfSale')
frappe.provide('inn.PointOfSale')

frappe.pages['pos-extended'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Point of Sales',
		single_column: true
	});

	page.add_menu_item(__("Change POS Profile"), () => dialog_pos_profile())

	function dialog_pos_profile() {
		me = this
		let d = new frappe.ui.Dialog({
			title: __('Change POS Profile'),
			fields: [
				{
					label: 'POS Opening Profile',
					fieldname: 'pos_profile_selected',
					fieldtype: 'Link',
					options: "POS Opening Entry",
					reqd: 1,
					get_query() {
						return {
							filters: {
								user: frappe.session.user,
								docstatus: 1,
								status: "Open"
							}
						}
					}
				}
			],
			size: 'large',
			primary_action_label: 'Select',
			primary_action(values) {
				d.hide();

				onScan.detachFrom(document);
				wrapper.pos.wrapper.html("");
				wrapper.pos.change_pos_profile(values.pos_profile_selected);
			},
		});


		d.show();
	}

	var file = location.pathname.split("/").pop();

	var link = document.createElement("link");
	link.href = file.substr(0, file.lastIndexOf(".")) + ".css";
	link.type = "text/css";
	link.rel = "stylesheet";
	link.media = "screen,print";

	document.getElementsByTagName("head")[0].appendChild(link);

	frappe.require(["point-of-sale.bundle.js", "inn-pos.bundle.js"], function () {
		inn.PointOfSale.Controller = class MyPosController extends erpnext.PointOfSale.Controller {
			constructor(wrapper) {
				super(wrapper);
			}

			change_pos_profile(profile_opening_name) {
				this.profile_opening_name = profile_opening_name
				this.check_opening_entry()
			}

			check_opening_entry() {
				this.fetch_opening_entry().then(async (r) => {
					if (r.message.length) {
						var pos_profile = undefined

						if (this.profile_opening_name == undefined) {
							await this.prepare_app_defaults(r.message[0]);
							pos_profile = r.message[0].pos_profile
						} else {
							for (let i = 0; i < r.message.length; i++) {
								if (r.message[i].name == this.profile_opening_name) {
									await this.prepare_app_defaults(r.message[i]);
									pos_profile = r.message[i].pos_profile
									return;
								}
							}
						}

						// handling select item group bug not filtering based on pos_profile
						// give timeout so frappe have a time to configuring all the basic process
						// idk why frappe not using async and await to handle the bug
						await new Promise(r => setTimeout(r, 400));
						var me = this
						this.item_selector.item_group_field.df.get_query = function () {
							return {
								query: 'erpnext.selling.page.point_of_sale.point_of_sale.item_group_query',
								filters: {
									pos_profile: me.frm.doc ? me.frm.doc.pos_profile : ''
								}
							}
						}

					} else {
						this.create_opening_voucher();
					}
				});
			}

			init_payments() {
				this.payment = new inn.PointOfSale.PosExtendedPayment({
					wrapper: this.$components_wrapper,
					events: {
						get_frm: () => this.frm || {},

						get_customer_details: () => this.customer_details || {},

						toggle_other_sections: (show) => {
							if (show) {
								this.item_details.$component.is(':visible') ? this.item_details.$component.css('display', 'none') : '';
								this.item_selector.toggle_component(false);
							} else {
								this.item_selector.toggle_component(true);
							}
						},

						submit_invoice: () => {
							this.frm.savesubmit()
								.then((r) => {
									this.toggle_components(false);
									this.order_summary.toggle_component(true);
									this.order_summary.load_summary_of(this.frm.doc, true);

									frappe.call({
										method: "inn.inn_hotels.page.pos_extended.pos_extended.save_pos_usage",
										args: {
											invoice_name: this.frm.doc.name,
											table: this.cart.table_number,
											action: "save_draft"
										},
										async: false
									})

									frappe.call({
										method: "inn.inn_hotels.page.pos_extended.pos_extended.clean_table_number",
										async: false,
										args: {
											invoice_name: this.frm.doc.name
										}
									})

									frappe.show_alert({
										indicator: 'green',
										message: __('POS invoice {0} created succesfully', [r.doc.name])
									});
								});
						}
					}
				});
			}

			async save_draft_invoice() {
				if (!this.$components_wrapper.is(":visible")) return;

				if (this.frm.doc.items.length == 0) {
					frappe.show_alert({
						message: __("You must add atleast one item to save it as draft."),
						indicator: 'red'
					});
					frappe.utils.play_sound("error");
					return;
				}

				if (!("table_number" in this.cart)) {
					frappe.show_alert({
						message: __("You must assign table to this order."),
						indicator: 'red'
					});
					frappe.utils.play_sound("error");
					return;
				}

				await this.frm.save(undefined, undefined, undefined, () => {
					frappe.show_alert({
						message: __("There was an error saving the document."),
						indicator: 'red'
					});
					frappe.utils.play_sound("error");
				}).then(() => {
					frappe.run_serially([
						() => frappe.call({
							method: "inn.inn_hotels.page.pos_extended.pos_extended.save_pos_usage",
							args: {
								invoice_name: this.frm.doc.name,
								table: this.cart.table_number,
								action: "save_draft"
							}
						}),
						() => frappe.dom.freeze(),
						() => this.make_new_invoice(),
						() => frappe.dom.unfreeze(),
					]);
				});
			}

			prepare_menu() {
				this.page.add_menu_item(__("Open Table Monitor"), () => {
					frappe.set_route("inn-pos-table")
				}, false, 'Ctrl+T');
				this.page.add_menu_item(__("Open Form View"), this.open_form_view.bind(this), false, 'Ctrl+F');
				this.page.add_menu_item(__("Toggle Recent Orders"), this.toggle_recent_order.bind(this), false, 'Ctrl+O');
				this.page.add_menu_item(__("Save as Draft"), this.save_draft_invoice.bind(this), false, 'Ctrl+S');
				this.page.add_menu_item(__('Close the POS'), this.close_pos.bind(this), false, 'Shift+Ctrl+C');
			}

			init_recent_order_list() {
				this.recent_order_list = new inn.PointOfSale.PosExtendedPastOrderList({
					wrapper: this.$components_wrapper,
					events: {
						open_invoice_data: (name) => {
							frappe.db.get_doc('POS Invoice', name).then((doc) => {
								this.order_summary.load_summary_of(doc);
							});
						},
						reset_summary: () => this.order_summary.toggle_summary_placeholder(true)
					}
				})
			}

            init_item_cart() {
                this.cart = new inn.PointOfSale.PosExtendItemCart({
                    wrapper: this.$components_wrapper,
                    settings: this.settings,
                    events: {
                        get_frm: () => this.frm,

                        cart_item_clicked: (item) => {
                            const item_row = this.get_item_from_frm(item);
                            this.item_details.toggle_item_details_section(item_row);
                        },

                        numpad_event: (value, action) => this.update_item_field(value, action),

                        checkout: () => this.save_and_checkout(),

                        edit_cart: () => this.payment.edit_cart(),

                        customer_details_updated: (details) => {
                            this.customer_details = details;
                            this.payment.render_loyalty_points_payment_mode();
                        },

                        print_captain_order: () => this.print_captain_order(),
                        print_table_order: () => this.print_table_order(),

                        transfer_folio: () => this.dialog_transfer_folio(),
                        transfer_charge_to_customer_dialog: () => {
                            this.dialog_transfer_charge_to_customer();
                        }
                    }
                })
            }
            dialog_transfer_charge_to_customer() {
                const frm_doc = this.frm.doc;
                if (!frm_doc.items || !frm_doc.items.length) {
                    frappe.show_alert({ message: __("Add items to the cart to transfer charge."), indicator: "orange" });
                    return;
                }
                const me = this;
                let d = new frappe.ui.Dialog({
                    title: __('Transfer Charge To Customer'),
                    fields: [
                        {
                            label: __('Grand Total'),
                            fieldname: 'grand_total_display',
                            fieldtype: 'Currency',
                            default: frm_doc.grand_total,
                            read_only: 1,
                            col: 6
                        },
                        {
                            label: __('Paying Customer'),
                            fieldname: 'paying_customer',
                            fieldtype: 'Link',
                            options: 'Customer',
                            reqd: 1,
                            col: 6,
                            description: __("Select the customer who will pay this bill.")
                        }
                    ],
                    size: 'small',
                    primary_action_label: __('Transfer Charge'),
                    primary_action(values) {
                        d.hide();
                        frappe.call({
                            method: 'inn.inn_hotels.page.pos_extended.pos_extended.transfer_charge_to_customer',
                            args: {
                                cart_data_str: JSON.stringify(frm_doc),
                                paying_customer: values.paying_customer,
                                original_customer: frm_doc.customer,
								pos_profile_name: frm_doc.pos_profile
                            },
                            freeze: true,
                            freeze_message: __("Processing charge transfer..."),
                            callback: function(r) {
                                if (r.message && r.message.status === "success") {
                                    frappe.show_alert({
                                        message: __("Charge transferred successfully to {0}. Journal Entry: {1}", [values.paying_customer, r.message.journal_entry]),
                                        indicator: "green"
                                    });

                                    me.make_new_invoice();

                                } else {
                                    frappe.msgprint({
                                        title: __('Error'),
                                        indicator: 'red',
                                        message: (r.message && r.message.error) ? r.message.error : __('Failed to transfer charge.')
                                    });
                                }
                            },
                            error: function(err) {
                                frappe.msgprint({
                                    title: __('Error'),
                                    indicator: 'red',
                                    message: __('An unexpected error occurred. Check console for details.')
                                });
                                console.error("Error in Python transfer_charge_to_customer call:", err);
                            }
                        });
                    }
                });
                d.show();
            }

			async save_and_checkout() {
				await super.save_and_checkout()

				frappe.call({
					method: "inn.inn_hotels.page.pos_extended.pos_extended.save_pos_usage",
					args: {
						invoice_name: this.frm.doc.name,
						table: this.cart.table_number,
						action: "save_draft"
					},
					async: true
				})
			}

			dialog_transfer_folio() {
				var me = this
				let d = new frappe.ui.Dialog({
					title: __('Transfer to Folio'),
					fields: [
						{
							label: __('Grand Total'),
							fieldname: 'grand_total_display',
							fieldtype: 'Currency',
							read_only: 1,
						},
						{
							label: __('Inn Folio'),
							fieldname: 'inn_folio_transfer',
							fieldtype: 'Link',
							options: "Inn Folio",
							reqd: 1,
							get_query() {
								return {
									filters: {
										status: "Open"
									}
								}
							}
						}
					],
					size: 'large',
					primary_action_label: __('Select'),
					primary_action(values) {
						d.hide();
						me.transfer_folio(values.inn_folio_transfer);
					},
				});

				const current_grand_total = me.frm.doc.grand_total;
				d.set_value('grand_total_display', current_grand_total);
				d.show();
			}

			transfer_folio(folio_id) {
				const frm_doc = this.frm.doc;
				frappe.run_serially([
					() => frappe.dom.freeze(),

					this.frm.savesubmit()
						.then((r) => {
							this.toggle_components(false);
							this.order_summary.toggle_component(true);
							// this.order_summary.load_summary_of(this.frm.doc, true);

							frappe.call({
								method: "inn.inn_hotels.page.pos_extended.pos_extended.save_pos_usage",
								args: {
									invoice_name: this.frm.doc.name,
									table: this.cart.table_number,
									action: "save_draft"
								},
								async: false
							})
							frappe.call({
								method: "inn.inn_hotels.page.pos_extended.pos_extended.clean_table_number",
								async: false,
								args: {
									invoice_name: this.frm.doc.name
								}
							})
							frappe.call({
								method: "inn.inn_hotels.page.pos_extended.pos_extended.transfer_to_folio",
								args: {
									invoice_doc: this.frm.doc,
									folio_name: folio_id,
									pos_profile_name: frm_doc.pos_profile

								},
								async: false,
							})
							frappe.show_alert({
								indicator: 'green',
								message: __('POS invoice {0} created succesfully', [r.doc.name])
							});
							this.order_summary.load_summary_of(this.frm.doc, true);
						}),
					() => frappe.dom.unfreeze()
				])

			}


			async print_table_order() {
				const me = this
				let success = false

				await frappe.call({
					method: "inn.inn_hotels.page.pos_extended.pos_extended.save_pos_usage",
					args: {
						invoice_name: this.frm.doc.name,
						table: this.cart.table_number,
						action: "print_table"
					},
					async: false,
					callback: r => {
						success = true
					}

				})
				if (success) {
					frappe.utils.print(
						me.frm.doc.doctype,
						me.frm.doc.name,
						"POS Extended Table Order",
						me.frm.doc.letter_head,
						me.frm.doc.language || frappe.boot.lang
					);
				}
			}

			async print_captain_order() {
				const me = this
				let success = false

				this.frm.dirty()

				await this.frm.save(undefined, undefined, undefined, () => {
					frappe.show_alert({
						message: __("There was an error saving the document."),
						indicator: 'red'
					});
					frappe.utils.play_sound("error");
				});

				await frappe.call({
					method: "inn.inn_hotels.page.pos_extended.pos_extended.save_pos_usage",
					args: {
						invoice_name: this.frm.doc.name,
						table: this.cart.table_number,
						action: "print_captain"
					},
					async: false,
					callback: r => {
						success = true
					}
				})
				if (success) {
					frappe.utils.print(
						me.frm.doc.doctype,
						me.frm.doc.name,
						"POS Extended Captain Order",
						me.frm.doc.letter_head,
						me.frm.doc.language || frappe.boot.lang
					);
				}
			}

			print_bill(draft) {
				frappe.utils.print(
					draft.doctype,
					draft.name,
					"POS Extended Bill",
					draft.letter_head,
					draft.language || frappe.boot.lang
				);
			}

			init_order_summary() {
				this.order_summary = new inn.PointOfSale.PosExtendPastOrderSummary({
					wrapper: this.$components_wrapper,
					settings: this.settings,
					events: {
						get_frm: () => this.frm,

						process_return: (name) => {
							this.recent_order_list.toggle_component(false);
							frappe.db.get_doc('POS Invoice', name).then((doc) => {
								frappe.run_serially([
									() => this.make_return_invoice(doc),
									() => this.cart.load_invoice(),
									() => this.item_selector.toggle_component(true)
								]);
							});
						},
						edit_order: (name) => {
							this.recent_order_list.toggle_component(false);
							frappe.run_serially([
								() => this.frm.refresh(name),
								() => this.frm.call('reset_mode_of_payments'),
								() => this.cart.load_invoice(),
								() => this.item_selector.toggle_component(true)
							]);
						},
						delete_order: (name) => {
							frappe.model.delete_doc(this.frm.doc.doctype, name, () => {
								this.recent_order_list.refresh_list();
							});
						},
						new_order: () => {
							frappe.run_serially([
								() => frappe.dom.freeze(),
								() => this.make_new_invoice(),
								() => this.item_selector.toggle_component(true),
								() => frappe.dom.unfreeze(),
							]);
						},
						print_bill: (doc) => this.print_bill(doc),
					}
				})
			}

			async on_cart_update(args) {
				frappe.dom.freeze();
				let item_row = undefined;
				try {
					let { field, value, item } = args;
					item_row = this.get_item_from_frm(item);
					const item_row_exists = !$.isEmptyObject(item_row);

					const from_selector = field === 'qty' && value === "+1";
					if (from_selector)
						value = flt(item_row.stock_qty) + flt(value);

					if (item_row_exists) {
						if (field === 'qty')
							value = flt(value);

						if (['qty', 'conversion_factor'].includes(field) && value > 0 && !this.allow_negative_stock) {
							const qty_needed = field === 'qty' ? value * item_row.conversion_factor : item_row.qty * value;
							await this.check_stock_availability(item_row, qty_needed, this.frm.doc.set_warehouse);
						}

						if (this.is_current_item_being_edited(item_row) || from_selector) {
							await frappe.model.set_value(item_row.doctype, item_row.name, field, value);
							this.update_cart_html(item_row);
						}

					} else {
						if (!this.frm.doc.customer)
							return this.raise_customer_selection_alert();

						if (!this.cart.table_number) {
							return this.raise_table_selection_alert()
						}


						const { item_code, batch_no, serial_no, rate, uom } = item;

						if (!item_code)
							return;

						const new_item = { item_code, batch_no, rate, uom, [field]: value };

						if (serial_no) {
							await this.check_serial_no_availablilty(item_code, this.frm.doc.set_warehouse, serial_no);
							new_item['serial_no'] = serial_no;
						}

						if (field === 'serial_no')
							new_item['qty'] = value.split(`\n`).length || 0;

						item_row = this.frm.add_child('items', new_item);

						if (field === 'qty' && value !== 0 && !this.allow_negative_stock) {
							const qty_needed = value * item_row.conversion_factor;
							await this.check_stock_availability(item_row, qty_needed, this.frm.doc.set_warehouse);
						}

						await this.trigger_new_item_events(item_row);

						this.update_cart_html(item_row);

						if (this.item_details.$component.is(':visible'))
							this.edit_item_details_of(item_row);

						if (this.check_serial_batch_selection_needed(item_row) && !this.item_details.$component.is(':visible'))
							this.edit_item_details_of(item_row);
					}

				} catch (error) {
				} finally {
					frappe.dom.unfreeze();
					return item_row; // eslint-disable-line no-unsafe-finally
				}
			}

			raise_table_selection_alert() {
				frappe.dom.unfreeze();
				frappe.show_alert({
					message: __('You must select a table before adding an item.'),
					indicator: 'orange'
				});
				frappe.utils.play_sound("error");
			}
		};

		wrapper.pos = new inn.PointOfSale.Controller(wrapper);
		window.cur_pos = wrapper.pos;
	})
}