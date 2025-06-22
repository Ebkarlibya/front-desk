// Copyright (c) 2025, Core Initiative and contributors
// For license information, please see license.txt

frappe.ui.form.on('Extend Reservation', {
    onload: function(frm) {
        // Set properties for child table
        frm.get_field('reservations_to_extend').grid.cannot_add_rows = true; // Prevent adding rows manually
        frm.get_field('reservations_to_extend').grid.only_sortable(); // Allow sorting but not adding/deleting

        // Ensure fields in Section 3 are initially disabled if no rows are populated
        toggle_bulk_update_fields(frm);
    },

    refresh: function(frm) {
        // Re-check and toggle fields on refresh
        toggle_bulk_update_fields(frm);
    },

    // Handle Populate button click
    populate_button: function(frm) { // 'populate_button' is the fieldname for the button
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
                        item.current_check_in = d.current_check_in;
                        item.current_check_out = d.current_check_out;
                        item.customer = d.customer;
                        item.room = d.room;
                        item.room_price = d.room_price;
                    });
                    frm.refresh_field('reservations_to_extend');
                    toggle_bulk_update_fields(frm); // Enable/disable fields after population
                    // frm.save(); // Optional: uncomment if you want to auto-save after populating
                } else {
                    frm.refresh_field('reservations_to_extend'); // Ensure empty table is refreshed
                    toggle_bulk_update_fields(frm); // Disable fields if no rows
                }
            }
        });
    },

    // Field change handlers for Section 3 (Bulk Update)
    new_customer: function(frm) {
        update_table_fields(frm, 'customer', frm.doc.new_customer);
    },
    new_date_start: function(frm) {
        update_table_fields(frm, 'current_check_in', frm.doc.new_date_start);
    },
    new_date_end: function(frm) {
        update_table_fields(frm, 'current_check_out', frm.doc.new_date_end);
    }
});

// Helper function to update fields in the child table
function update_table_fields(frm, field_to_update, new_value) {
    if (frm.doc.reservations_to_extend && new_value) { // Only update if new_value is not empty
        $.each(frm.doc.reservations_to_extend || [], function(i, row) {
            // Check if the row is selected to apply the bulk update
            if (row.idx && frm.get_field("reservations_to_extend").grid.get_selected().includes(row.name)) {
                 row[field_to_update] = new_value;
            }
        });
        frm.refresh_field('reservations_to_extend');
    }
}

// Helper function to enable/disable bulk update fields
function toggle_bulk_update_fields(frm) {
    let has_rows = frm.doc.reservations_to_extend && frm.doc.reservations_to_extend.length > 0;
    frm.set_df_property('new_customer', 'read_only', !has_rows);
    frm.set_df_property('new_date_start', 'read_only', !has_rows);
    frm.set_df_property('new_date_end', 'read_only', !has_rows);
}
