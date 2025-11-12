// Copyright (c) 2020, Core Initiative and contributors
// For license information, please see license.txt
frappe.ui.form.on("AR City Ledger Invoice", {
  onload: function (frm) {
    set_payment_entry_query(frm);
    make_payment_visibility(frm);
  },
  refresh: function (frm) {
    set_payment_entry_query(frm);
    filter_folio(frm);
    make_payment_visibility(frm);
  },
  inn_channel: function (frm) {
    filter_folio(frm);
  },
  inn_group: function (frm) {
    filter_folio(frm);
  },
  customer_id: function (frm) {
    set_payment_entry_query(frm);
    filter_folio(frm);
    calculate_payments(frm);
  },
  make_payment: function (frm) {
    frappe.confirm(
      __("Please make sure that the payment details (") +
        "<b>" +
        __("Payment Date, Amount and Mode of Payment") +
        "</b>" +
        __(") are correct, and ") +
        "<b>" +
        __("Outstanding Amount is zero") +
        "</b>" +
        ". Are you want to continue?",
      function () {
        // if (frm.doc.outstanding != 0.0) {
        //   frappe.msgprint(
        //     __("Outstanding amount must be zero in order to Make Payment. Please correct the payment details before Making Payment.")
        // );
        // } else {
        frappe.call({
          method:
            "inn.inn_hotels.doctype.ar_city_ledger_invoice.ar_city_ledger_invoice.make_payment",
          args: {
            id: frm.doc.name,
          },
          callback: (r) => {
            if (r.message === 1) {
              frappe.show_alert(
                __("This AR City Ledger Invoice are successfully paid.")
              );
              frm.reload_doc();
            }
          },
        });
        // }
      }
    );
  },
});

// --------------------------- Set query for Payment Entry child table ---------------------------
function set_payment_entry_query(frm) {
  if (!frm.fields_dict["ar_city_ledger_invoice_payment_entry"]) return;

  let field = frm.fields_dict["ar_city_ledger_invoice_payment_entry"].grid.fields_map["payment_entry_id"];
  if (!field) return;

  field.get_query = function () {
    if (!frm.doc.customer_id) {
      return {
        filters: [
          ["Payment Entry", "name", "=", ""]
        ]
      };
    }

    return {
      filters: [
        ["Payment Entry", "party", "=", frm.doc.customer_id],
        ["Payment Entry", "party_type", "=", "Customer"],
        ["Payment Entry", "docstatus", "=", 1],
        ["Payment Entry", "payment_type", "=", "Receive"]
      ]
    };
  };
}

// --------------------------- Parent add/remove handlers ---------------------------
frappe.ui.form.on("AR City Ledger Invoice", "payments_add", function (frm) {
  if (!frm.doc.folio || frm.doc.folio.length === 0) {
    frappe.msgprint(__("Please add Folio to be Collected first"));
    frm.doc.payments = [];
    frm.refresh_field("payments");
  } else {
    calculate_payments(frm);
  }
});
frappe.ui.form.on("AR City Ledger Invoice", "payments_remove", function (frm) {
  calculate_payments(frm);
});
frappe.ui.form.on("AR City Ledger Invoice", "ar_city_ledger_invoice_payment_entry_add", function (frm) {
    // prevent adding payment entry when no folio
  if (!frm.doc.folio || frm.doc.folio.length === 0) {
    frappe.msgprint(__("Please add Folio to be Collected first"));
    frm.doc.ar_city_ledger_invoice_payment_entry = [];
    frm.refresh_field("ar_city_ledger_invoice_payment_entry");
  } else {
    calculate_payments(frm);
  }
});
frappe.ui.form.on("AR City Ledger Invoice", "ar_city_ledger_invoice_payment_entry_remove", function (frm) {
  calculate_payments(frm);
});

// Child doctype handlers (field-level triggers)
frappe.ui.form.on("AR City Ledger Invoice Folio", {
  folio_id: function (frm, cdt, cdn) {
    let child = locals[cdt][cdn];
    autofill_by_folio(child);
  },
  folio_remove: function (frm) {
    calculate_payments(frm);
  },
});

frappe.ui.form.on("AR City Ledger Invoice Payments", {
  // called when a payment row is added via child doctype handler (fallback)
  payments_add: function (frm) {
    if (!frm.doc.folio || frm.doc.folio.length === 0) {
      frappe.msgprint(__("Please add Folio to be Collected first"));
      frm.doc.payments = [];
      frm.refresh_field("payments");
    }
  },
  payments_remove: function (frm) {
    calculate_payments(frm);
  },
  payment_amount: function (frm, cdt, cdn) {
    let child = locals[cdt][cdn];
    if (child) {
      enforce_overpayment_limit_for_payment_child(frm, child, "payments");
    }
  },
  print_payment: function (frm, cdt, cdn) {
    let child = locals[cdt][cdn];
    print_payment_receipt(frm, child);
  },
  // before_payments_remove: function (frm, cdt, cdn) {
  //   let child = locals[cdt][cdn];
  //   console.log(child);
  //   if (child.paid === 1 && child.journal_entry_id) {
  //     frappe.confirm(
  //       __(
  //         `This payment has been paid. and connected with a Journal entry ${child.journal_entry_id}. Are you sure you want to remove it? (Removing the entry will cause the journal entry to be cancelled as well)`
  //       ),

  //       function () {
  //         // User confirmed, allow removal
  //         frappe.call({
  //           method: "cancel_ar_city_ledger_invoice",
  //           args: {
  //             jv_id: child.journal_entry_id,
  //             arci_id: frm.doc.name,
  //           },
  //           freeze: true,
  //           freeze_message: __("Removing Payment..."),
  //           callback: function (r) {
  //             if (r.message) {
  //               frappe.show_alert(__("Payment removed successfully."));
  //               frm.remove_child("payments", child);
  //               frm.refresh_field("payments");
  //               calculate_payments(frm);
  //               frm.save();
  //             }
  //           },
  //         });
  //       },
  //       function () {
  //         // User cancelled, prevent removal
  //         frappe.throw("Payment removal cancelled.");
  //       }
  //     );
  //   }
  // },
  mode_of_payment: function (frm, cdt, cdn) {
    let child = locals[cdt][cdn];
    if (child.mode_of_payment) {
      autofill_payments_account(child);
    }
  },
});

// --------------------------- Payment Entry table handlers ---------------------------
frappe.ui.form.on("AR City Ledger Invoice Payment Entry", {
  payment_entry_id: function (frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    if (!row.payment_entry_id) {
      row.payment_amount = 0;
      frm.refresh_field("ar_city_ledger_invoice_payment_entry");
      calculate_payments(frm);
      return;
    }

    if (!frm.doc.customer_id) {
      frappe.msgprint(__("Please select Contact Person (customer) before choosing Payment Entry."));
      row.payment_entry_id = "";
      row.payment_amount = 0;
      frm.refresh_field("ar_city_ledger_invoice_payment_entry");
      return;
    }

    frappe.call({
      method: "inn.inn_hotels.doctype.ar_city_ledger_invoice.ar_city_ledger_invoice.get_payment_entry_remaining",
      args: {
        payment_entry_id: row.payment_entry_id,
        current_arci: frm.doc.name || ""
      },
      callback: function (r) {
        try {
          if (!r || !r.message) {
            frappe.msgprint(__("Unable to validate Payment Entry. Please try again."));
            row.payment_entry_id = "";
            row.payment_amount = 0;
            frm.refresh_field("ar_city_ledger_invoice_payment_entry");
            calculate_payments(frm);
            return;
          }

          if (r.message.error) {
            frappe.msgprint(__(r.message.error));
            row.payment_entry_id = "";
            row.payment_amount = 0;
            frm.refresh_field("ar_city_ledger_invoice_payment_entry");
            calculate_payments(frm);
            return;
          }

          let pe_amount = flt(r.message.pe_amount || 0);
          let remaining_excluding_other_arcis = flt(r.message.remaining || 0);

          // sum allocations in THIS ARCI for same PE excluding current row
          let sum_in_this_doc_other_rows = 0.0;
          if (frm.doc.ar_city_ledger_invoice_payment_entry && frm.doc.ar_city_ledger_invoice_payment_entry.length) {
            frm.doc.ar_city_ledger_invoice_payment_entry.forEach(function (pe_row) {
              if (pe_row.name !== row.name && pe_row.payment_entry_id === row.payment_entry_id) {
                sum_in_this_doc_other_rows += flt(pe_row.payment_amount);
              }
            });
          }

          // allowed for this row = remaining_excluding_other_arcis - sum_in_this_doc_other_rows
          let allowed_for_row = remaining_excluding_other_arcis - sum_in_this_doc_other_rows;
          if (allowed_for_row <= 0) {
            frappe.msgprint(__("This Payment Entry is already fully allocated and cannot be linked."));
            row.payment_entry_id = "";
            row.payment_amount = 0;
            frm.refresh_field("ar_city_ledger_invoice_payment_entry");
            calculate_payments(frm);
            return;
          }

          let allowed_display = allowed_for_row.toFixed(2);

          if (allowed_for_row < pe_amount) {
            let msg = __("This Payment Entry has only {0} remaining (after other allocations). The payment amount has been set to {0}.");
            msg = msg.replace(/\{0\}/g, allowed_display);
            frappe.msgprint(msg);
            row.payment_amount = allowed_for_row;
          } else {
            row.payment_amount = pe_amount;
          }

          // ensure not exceeding allowed_for_row (in case user prefilled)
          if (flt(row.payment_amount) > allowed_for_row) {
            row.payment_amount = allowed_for_row;
          }

          frm.refresh_field("ar_city_ledger_invoice_payment_entry");
          calculate_payments(frm);
        } catch (err) {
          console.error("Error in payment_entry_id callback:", err);
          frappe.msgprint(__("Error validating Payment Entry. See console for details."));
        }
      }
    });
  },
  payment_amount: function (frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (!row) return;

    if (!row.payment_entry_id) {
      enforce_overpayment_limit_for_payment_child(frm, row, "ar_city_ledger_invoice_payment_entry");
      return;
    }

    frappe.call({
      method: "inn.inn_hotels.doctype.ar_city_ledger_invoice.ar_city_ledger_invoice.get_payment_entry_remaining",
      args: {
        payment_entry_id: row.payment_entry_id,
        current_arci: frm.doc.name || ""
      },
      callback: function (r) {
        try {
          if (!r || !r.message || r.message.error) {
            enforce_overpayment_limit_for_payment_child(frm, row, "ar_city_ledger_invoice_payment_entry");
            return;
          }

          let remaining_excluding_other_arcis = flt(r.message.remaining || 0);

          // sum of other rows in THIS doc for same PE (exclude current row)
          let sum_in_this_doc_other_rows = 0.0;
          if (frm.doc.ar_city_ledger_invoice_payment_entry && frm.doc.ar_city_ledger_invoice_payment_entry.length) {
            frm.doc.ar_city_ledger_invoice_payment_entry.forEach(function (pe_row) {
              if (pe_row.name !== row.name && pe_row.payment_entry_id === row.payment_entry_id) {
                sum_in_this_doc_other_rows += flt(pe_row.payment_amount);
              }
            });
          }

          let allowed_for_row = remaining_excluding_other_arcis - sum_in_this_doc_other_rows;
          if (allowed_for_row < 0) allowed_for_row = 0.0;

          if (flt(row.payment_amount) > allowed_for_row) {
            let allowed_display = allowed_for_row.toFixed(2);
            let msg = __("Payment Amount exceeds the remaining amount for this Payment Entry. It has been adjusted to {0}.");
            msg = msg.replace(/\{0\}/g, allowed_display);
            frappe.msgprint(msg);

            row.payment_amount = allowed_for_row;
            frm.refresh_field("ar_city_ledger_invoice_payment_entry");
          }

          enforce_overpayment_limit_for_payment_child(frm, row, "ar_city_ledger_invoice_payment_entry");
        } catch (err) {
          console.error("Error in payment_amount callback:", err);
          enforce_overpayment_limit_for_payment_child(frm, row, "ar_city_ledger_invoice_payment_entry");
        }
      }
    });
  },

  payment_entry_add: function (frm) {
    // nothing until user selects PE
  },

  payment_entry_remove: function (frm) {
    calculate_payments(frm);
  }
});

// --------------------------- Query for Mode of Payment in payments table ---------------------------
cur_frm.set_query("mode_of_payment", "payments", function (doc, cdt, cdn) {
  var d = locals[cdt][cdn];
  return {
    filters: [["Mode of Payment", "mode_of_payment", "!=", "City Ledger"]],
  };
});

// --------------------------- Filter Folio list by channel/group/customer ---------------------------
function filter_folio(frm) {
  let field = frm.fields_dict["folio"].grid.fields_map["folio_id"];
  let channel = frm.doc.inn_channel;
  let group = frm.doc.inn_group;
  let customer_id = frm.doc.customer_id;
  frappe.call({
    method:
      "inn.inn_hotels.doctype.ar_city_ledger.ar_city_ledger.get_folio_from_ar_city_ledger",
    args: {
      selector: "Folio",
      channel: channel,
      group: group,
      customer_id: customer_id,
    },
    callback: (r) => {
      if (r.message) {
        field.get_query = function () {
          return {
            filters: [["Inn Folio", "name", "in", r.message]],
          };
        };
      }
    },
  });
}

// --------------------------- Autofill folio details ---------------------------
function autofill_by_folio(child) {
  if (child.folio_id !== undefined) {
    frappe.call({
      method:
        "inn.inn_hotels.doctype.ar_city_ledger.ar_city_ledger.get_ar_city_ledger_by_folio",
      args: {
        folio_id: child.folio_id,
      },
      callback: (r) => {
        if (r.message) {
          child.customer_id = r.message.customer_id;
          child.amount = r.message.total_amount;
          child.open = r.message.folio_open;
          child.close = r.message.folio_close;
          child.ar_city_ledger_id = r.message.name;
          cur_frm.refresh_field("folio");

          if (child.amount != 0) {
            calculate_payments(cur_frm);
          }
        }
      },
    });
  }
}

// --------------------------- Calculate totals: total_amount, total_paid, outstanding ---------------------------
function calculate_payments(frm) {
  let total_amount = 0.0;
  let total_paid = 0.0;
  let outstanding = 0.0;

  // Folios
  if (frm.doc.folio && frm.doc.folio.length > 0) {
    frm.doc.folio.forEach((f) => {
      if (f.amount !== undefined && f.amount !== null && f.amount !== "") {
        total_amount += flt(f.amount);
      }
    });
  }

  // Payments table
  if (frm.doc.payments && frm.doc.payments.length > 0) {
    frm.doc.payments.forEach((p) => {
      if (p.payment_amount !== undefined && p.payment_amount !== null && p.payment_amount !== "") {
        total_paid += flt(p.payment_amount);
      }
    });
  }

  // Payment Entry table (fieldname in parent is ar_city_ledger_invoice_payment_entry)
  if (frm.doc.ar_city_ledger_invoice_payment_entry && frm.doc.ar_city_ledger_invoice_payment_entry.length > 0) {
    frm.doc.ar_city_ledger_invoice_payment_entry.forEach((pe) => {
      if (pe.payment_amount !== undefined && pe.payment_amount !== null && pe.payment_amount !== "") {
        total_paid += flt(pe.payment_amount);
      }
    });
  }

  outstanding = total_amount - total_paid;

  // Avoid negative outstanding shown due to float errors
  if (Math.abs(outstanding) < 0.000001) outstanding = 0.0;

  frm.set_value("total_amount", total_amount);
  frm.set_value("total_paid", total_paid);
  frm.set_value("outstanding", outstanding);
}

// --------------------------- Enforce outstanding protection for child rows ---------------------------
function enforce_overpayment_limit_for_payment_child(frm, child, parent_table_fieldname) {
  // حساب إجمالي الفوليوهات
  let total_amount = 0.0;
  if (frm.doc.folio) {
    frm.doc.folio.forEach((f) => {
      if (f.amount !== undefined && f.amount !== null && f.amount !== "") total_amount += flt(f.amount);
    });
  }

  let other_paid = 0.0;

  if (frm.doc.payments) {
    frm.doc.payments.forEach((p) => {
      if (p.name !== child.name && p.payment_amount) other_paid += flt(p.payment_amount);
    });
  }

  if (frm.doc.ar_city_ledger_invoice_payment_entry) {
    frm.doc.ar_city_ledger_invoice_payment_entry.forEach((pe) => {
      if (pe.name !== child.name && pe.payment_amount) other_paid += flt(pe.payment_amount);
    });
  }

  let allowed = total_amount - other_paid;
  if (allowed < 0) allowed = 0.0;

  let current_val = flt(child.payment_amount);

  if (current_val > allowed) {
    let allowed_display = allowed.toFixed(2);
    let msg = __("The amount paid exceeds the Outstanding. The amount has been adjusted to the remaining balance: {0}");
    msg = msg.replace(/\{0\}/g, allowed_display);
    frappe.msgprint(msg);

    child.payment_amount = allowed;

    if (parent_table_fieldname === "payments") {
      frm.refresh_field("payments");
    } else {
      frm.refresh_field("ar_city_ledger_invoice_payment_entry");
    }
  }

  calculate_payments(frm);
}

// helper flt to avoid depending on frappe.utils.flt in client scope
function flt(val) {
  if (val === null || val === undefined || val === "") return 0.0;
  if (typeof val === "string") {
    val = val.replace(/,/g, "");
  }
  val = Number(val);
  return isNaN(val) ? 0.0 : val;
}

// --------------------------- autofill payments account ---------------------------
function autofill_payments_account(child) {
  frappe.call({
    method:
      "inn.inn_hotels.doctype.ar_city_ledger_invoice.ar_city_ledger_invoice.get_payments_accounts",
    args: {
      mode_of_payment: child.mode_of_payment,
    },
    callback: (r) => {
      if (r.message) {
        child.account = r.message[0];
        child.account_against = r.message[1];
        cur_frm.refresh_field("payments");
      }
    },
  });
}

// --------------------------- visibility & disable when Paid ---------------------------
function make_payment_visibility(frm) {
  // hide sb5 if new or if both payments & payment_entry are empty, or if Paid
  if (frm.doc.__islocal === 1) {
    frm.set_df_property("sb5", "hidden", 1);
  } else if (
    (frm.doc.payments && frm.doc.payments.length === 0) &&
    (!frm.doc.ar_city_ledger_invoice_payment_entry || frm.doc.ar_city_ledger_invoice_payment_entry.length === 0)
  ) {
    frm.set_df_property("sb5", "hidden", 1);
  } else if (frm.doc.status == "Paid") {
    frm.set_df_property("sb5", "hidden", 1);
    disable_form(frm);
  } else {
    frm.set_df_property("sb5", "hidden", 0);
  }
}

// --------------------------- Print payment receipt ---------------------------
function print_payment_receipt(frm, child) {
  // Get the AR City Ledger Invoice Receipt Format from Inn Hotels Setting
  frappe.call({
    method: "frappe.client.get_value",
    args: {
      doctype: "Inn Hotels Setting",
      fieldname: "ar_city_ledger_invoice_dp",
    },
    callback: function (r) {
      let print_format = (r.message && r.message.ar_city_ledger_invoice_dp) || "Standard";
      frappe.set_route("print", "AR City Ledger Invoice Payments", child.name, {
        print_format: print_format,
        no_letterhead: 0,
        trigger_print: 1,
      });
    },
  });
}

// --------------------------- disable form when Paid ---------------------------
function disable_form(frm) {
  frm.disable_save();
  frm.set_df_property("issued_date", "read_only", 1);
  frm.set_df_property("due_date", "read_only", 1);
  frm.set_df_property("inn_channel", "read_only", 1);
  frm.set_df_property("inn_group", "read_only", 1);
  frm.set_df_property("customer_id", "read_only", 1);
  if (frm.get_field("folio")) frm.get_field("folio").grid.only_sortable();

  try {
    frappe.meta.get_docfield("AR City Ledger Invoice Payments", "payment_reference_date", frm.doc.name).read_only = 1;
    frappe.meta.get_docfield("AR City Ledger Invoice Payments", "mode_of_payment", frm.doc.name).read_only = 1;
    frappe.meta.get_docfield("AR City Ledger Invoice Payments", "payment_amount", frm.doc.name).read_only = 1;
    frappe.meta.get_docfield("AR City Ledger Invoice Payments", "payment_reference_no", frm.doc.name).read_only = 1;
    frappe.meta.get_docfield("AR City Ledger Invoice Payments", "payment_clearance_date", frm.doc.name).read_only = 1;
  } catch (e) {}

  try {
    frappe.meta.get_docfield("AR City Ledger Invoice Payment Entry", "payment_entry_id", frm.doc.name).read_only = 1;
    frappe.meta.get_docfield("AR City Ledger Invoice Payment Entry", "payment_amount", frm.doc.name).read_only = 1;
  } catch (e) {}

  frm.set_intro("This AR City Ledger Invoice has been Paid.");
}
