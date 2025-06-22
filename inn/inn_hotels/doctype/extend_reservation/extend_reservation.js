frappe.ui.form.on('Extend Reservation', {
    onload: function(frm) {
        // Set properties for child table
        frm.get_field('reservations_to_extend').grid.cannot_add_rows = true; // Prevent adding rows manually
        frm.get_field('reservations_to_extend').grid.only_sortable(); // Allow sorting but not adding/deleting

        // Ensure fields in Section 3 are initially disabled if no rows are populated
        toggle_bulk_update_fields(frm);

        // Add a custom button for "Submit" if the status is not already "Submitted"
        if (frm.doc.docstatus === 0) { // DocStatus 0 means Draft
             frm.add_custom_button(__('Submit Extensions'), () => {
                frm.save('Submit'); // Trigger the submit action
            }, __("Actions"));
        } else if (frm.doc.docstatus === 1) { // DocStatus 1 means Submitted
            frm.disable_save(); // Disable save for submitted docs
            frm.set_read_only(); // Make all fields read-only
        }
    },

    refresh: function(frm) {
        // Re-check and toggle fields on refresh
        toggle_bulk_update_fields(frm);
        
        // Hide/show submit button based on docstatus and if any rows are present
        if (frm.doc.docstatus === 0 && frm.doc.reservations_to_extend.length > 0) {
            frm.toggle_enable_btn('Submit Extensions', true);
        } else {
            frm.toggle_enable_btn('Submit Extensions', false);
        }
        
        // Hide/show Populate button based on docstatus
        if (frm.doc.docstatus === 1) { // Submitted
            frm.set_df_property('populate_button', 'hidden', 1);
            // Also hide bulk update fields
            frm.set_df_property('new_customer', 'hidden', 1);
            frm.set_df_property('new_date_start', 'hidden', 1);
            frm.set_df_property('new_date_end', 'hidden', 1);
            frm.set_df_property('section_bulk_update', 'hidden', 1); // Hide the entire section break
        } else {
            frm.set_df_property('populate_button', 'hidden', 0);
            frm.set_df_property('new_customer', 'hidden', 0);
            frm.set_df_property('new_date_start', 'hidden', 0);
            frm.set_df_property('new_date_end', 'hidden', 0);
            frm.set_df_property('section_bulk_update', 'hidden', 0);
        }
    },

    // Handle Populate button click
    populate_button: function(frm) {
        frm.set_value('reservations_to_extend', []); // Clear existing rows before populating

        frappe.call({
            method: 'inn.inn_hotels.doctype.extend_reservation.extend_reservation.populate_reservations_for_extension',
            args: {
                customer_filter: frm.doc.customer_filter,
                date_start_filter: frm.doc.date_start_filter,
                date_end_filter: frm.doc.date_end_filter
            },
            callback: (r) => {
                if (r.message) {
                    $.each(r.message, function(i, d) {
                        let item = frm.add_child('reservations_to_extend');
                        item.reservation = d.reservation;
                        item.original_check_in = d.original_check_in;
                        item.original_check_out = d.original_check_out;
                        item.customer = d.customer;
                        item.room = d.room;
                        item.room_price = d.room_price;
                        item.new_check_in = d.new_check_in; 
                        item.new_check_out = d.new_check_out; 
                    });
                    frm.refresh_field('reservations_to_extend');
                    toggle_bulk_update_fields(frm); 
                    frm.toggle_enable_btn('Submit Extensions', true); // Enable submit button after population
                } else {
                    frm.refresh_field('reservations_to_extend'); 
                    toggle_bulk_update_fields(frm); 
                    frm.toggle_enable_btn('Submit Extensions', false); // Disable submit if no rows
                }
            }
        });
    },

    // Field change handlers for Section 3 (Bulk Update)
    new_customer: function(frm) {
        // Update 'customer' field in all child rows
        update_table_fields(frm, 'customer', frm.doc.new_customer);
    },
    new_date_start: function(frm) { 
        // Update 'new_check_in' field in all child rows
        update_table_fields(frm, 'new_check_in', frm.doc.new_date_start);
    },
    new_date_end: function(frm) { 
        // Update 'new_check_out' field in all child rows
        update_table_fields(frm, 'new_check_out', frm.doc.new_date_end);
    }
});

// Helper function to update fields in the child table for ALL rows
function update_table_fields(frm, field_to_update, new_value) {
    // Only proceed if there are child rows and a new_value is provided (not null/undefined/empty string)
    // Check if new_value is explicitly not null/undefined for links and dates
    if (frm.doc.reservations_to_extend && frm.doc.reservations_to_extend.length > 0 && new_value !== null && new_value !== undefined && new_value !== '') { 
        // Iterate over ALL child rows (frm.doc.child_table_fieldname gives all rows)
        $.each(frm.doc.reservations_to_extend, function(i, row) {
            // Direct assignment to the property. This is often more reliable for bulk updates
            // followed by a refresh. Frappe's UI layer will then pick up this change.
            row[field_to_update] = new_value; 
        });
        frm.refresh_field('reservations_to_extend'); // Refresh the entire child table grid to show changes
    } else if (new_value === null || new_value === undefined || new_value === '') {
        // Handle cases where the main field is cleared,
        // you might want to clear the corresponding child fields too
        if (frm.doc.reservations_to_extend && frm.doc.reservations_to_extend.length > 0) {
            $.each(frm.doc.reservations_to_extend, function(i, row) {
                row[field_to_update] = new_value; // Set to empty/null
            });
            frm.refresh_field('reservations_to_extend');
        }
    }
}

// Helper function to enable/disable bulk update fields
function toggle_bulk_update_fields(frm) {
    let has_rows = frm.doc.reservations_to_extend && frm.doc.reservations_to_extend.length > 0;
    frm.set_df_property('new_customer', 'read_only', !has_rows);
    frm.set_df_property('new_date_start', 'read_only', !has_rows); 
    frm.set_df_property('new_date_end', 'read_only', !has_rows); 
}

// Function to set Audit Date (Keep this as it was provided originally)
function set_audit_date(frm) {
    frappe.call({
        method: 'inn.inn_hotels.doctype.inn_audit_log.inn_audit_log.get_last_audit_date',
        callback: (r) => {
            if (r.message) {
                if (frm.doc.__islocal === 1) {
                    frm.set_value('audit_date', r.message);
                }
            }
        }
    });
}