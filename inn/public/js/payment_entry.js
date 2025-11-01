
frappe.ui.form.on("Payment Entry", {

    // Handle custom_get_city_ledger_invoice button click (the 'options' value from JSON)
    custom_get_city_ledger_invoice: function (frm) { 
        // Check if customer is selected
        if (!frm.doc.party || frm.doc.party_type !== "Customer") {
            frappe.msgprint(__("Please select a Customer in the 'Party' field and ensure 'Party Type' is 'Customer'."));
            return;
        }
        if (!frm.doc.company) {
            frappe.msgprint(__("Please select a Company first."));
            return;
        }

        frappe.call({
            method: "inn.overrides.payment_entry.get_unpaid_city_ledger_invoices",
            args: {
                customer_id: frm.doc.party, 
                company: frm.doc.company,
            },
            callback: (r) => {
                if (r.message && r.message.length > 0) {
                    frm.clear_table("custom_unpaid_city_ledger_invoice"); // Clear existing
                    r.message.forEach(item => {
                        let new_row = frm.add_child("custom_unpaid_city_ledger_invoice");
                        new_row.reference_doctype = item.reference_doctype;
                        new_row.reference_name = item.reference_name;
                        new_row.total_amount = item.total_amount;
                        new_row.outstanding_amount = item.outstanding_amount;
                        new_row.allocated_amount = 0.0; // Initially 0
                    });
                    frm.refresh_field("custom_unpaid_city_ledger_invoice");
                    distribute_paid_amount_to_city_ledger(frm); // Distribute amount after populating
                    calculate_city_ledger_allocated_amount(frm); // Update totals
                } else {
                    frappe.msgprint(__("No unpaid AR City Ledger Invoices found for this customer."), 'blue');
                    frm.clear_table("custom_unpaid_city_ledger_invoice");
                    frm.refresh_field("custom_unpaid_city_ledger_invoice");
                    calculate_city_ledger_allocated_amount(frm); // Update totals (will be 0)
                }
            }
        });
    },
    
    // Trigger distribution when main Payment Entry's amount changes
    paid_amount: function(frm) {
        distribute_paid_amount_to_city_ledger(frm);
    },
    base_paid_amount: function(frm) { // Also trigger on base_paid_amount if it's the source
        distribute_paid_amount_to_city_ledger(frm);
    }
});

frappe.ui.form.on("Unpaid City Ledger Invoice", {
    allocated_amount: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        // تأكد من كون القيم أرقام
        let allocated = parseFloat(row.allocated_amount) || 0;
        let outstanding = parseFloat(row.outstanding_amount) || 0;

        if (allocated > outstanding) {
            // استخدم replace بدل .format لأن __() لا يضمن وجود .format
            let msg = __("Allocated amount ({0}) for invoice '{1}' cannot exceed its outstanding amount ({2}).");
            msg = msg.replace("{0}", allocated).replace("{1}", row.reference_name).replace("{2}", outstanding);

            frappe.msgprint(msg, __("Over-allocation Warning"));

            // عدّل القيمة بطريقة تثير حدث التحديث الصحيح
            frappe.model.set_value(cdt, cdn, 'allocated_amount', outstanding);

            // حدث تحديث الجدول بالكامل
            frm.refresh_field('custom_unpaid_city_ledger_invoice');

            // حدّث المجموع إن كان لديك حقل للمجموع
            let total = calculate_city_ledger_allocated_amount(frm);
            if (frm.doc.hasOwnProperty('custom_total_allocated_city_ledger')) {
                frm.set_value('custom_total_allocated_city_ledger', total);
            }
        } else {
            // عشان لو المستخدم غيّر قيمة بشكل صحيح نحدّث المجموع
            let total = calculate_city_ledger_allocated_amount(frm);
            if (frm.doc.hasOwnProperty('custom_total_allocated_city_ledger')) {
                frm.set_value('custom_total_allocated_city_ledger', total);
            }
        }
    },
});
// Helper function to calculate total allocated for City Ledger Invoices
function calculate_city_ledger_allocated_amount(frm) {
    let total_allocated = 0;
    if (frm.doc.custom_unpaid_city_ledger_invoice) {
        for (let row of frm.doc.custom_unpaid_city_ledger_invoice) {
            total_allocated += (row.allocated_amount || 0);
        }
    }
    return total_allocated;
}

// Helper function to distribute main Payment Entry's amount to City Ledger Invoices
function distribute_paid_amount_to_city_ledger(frm) {
    let paid_amount = frm.doc.paid_amount || 0; // The total amount paid in the Payment Entry
    let remaining_amount_to_distribute = paid_amount;

    if (!frm.doc.custom_unpaid_city_ledger_invoice || frm.doc.custom_unpaid_city_ledger_invoice.length === 0) {
        return; // No invoices to allocate to
    }

    // Sort invoices by outstanding_amount (smallest first) or due_date (earliest first) for optimal allocation
    // For now, process in the order they were populated.
    
    for (let row of frm.doc.custom_unpaid_city_ledger_invoice) {
        let outstanding = row.outstanding_amount || 0;
        let amount_to_allocate = 0;

        if (remaining_amount_to_distribute <= 0) {
            row.allocated_amount = 0; // No more to distribute
            continue;
        }

        if (remaining_amount_to_distribute >= outstanding) {
            // Allocate full outstanding amount
            amount_to_allocate = outstanding;
        } else {
            // Allocate only the remaining amount that can be distributed
            amount_to_allocate = remaining_amount_to_distribute;
        }

        row.allocated_amount = amount_to_allocate;
        remaining_amount_to_distribute -= amount_to_allocate;
    }
    frm.refresh_field("custom_unpaid_city_ledger_invoice");
    // No need to call calculate_city_ledger_allocated_amount here directly for return,
    // as it's triggered by on_change_item and frm.refresh_field implicitly.
}
