# Copyright (c) 2025, Core Initiative and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, add_days # Make sure getdate is imported

class ExtendReservation(Document):
    pass

@frappe.whitelist()
def populate_reservations_for_extension(customer_filter=None, date_start_filter=None, date_end_filter=None):
    """
    Fetches eligible Inn Reservations based on provided filters
    and returns them to populate the 'reservations_to_extend' table.
    """
    
    filters = {}
    
    # Apply customer filter if provided
    if customer_filter:
        filters["customer_id"] = customer_filter # Corrected: Use customer_id as per Inn Reservation DocType
    
    # Apply date range filters if provided
    # Assuming date_start_filter and date_end_filter apply to expected_arrival date
    if date_start_filter:
        filters["expected_arrival"] = [">=", getdate(date_start_filter)] # Corrected field name
    if date_end_filter:
        if "expected_arrival" in filters:
            # If date_start_filter is already applied, combine conditions
            filters["expected_arrival"] = ["between", (getdate(date_start_filter), getdate(date_end_filter))] # Corrected field name
        else:
            # Apply only date_end_filter
            filters["expected_arrival"] = ["<=", getdate(date_end_filter)] # Corrected field name

    # Fetch reservations that are currently "In House" or "Check In"
    filters["status"] = ["in", ["In House", "Check In"]] 

    reservations = frappe.get_list(
        "Inn Reservation",
        filters=filters,
        fields=[
            "name",              # Reservation ID
            "expected_arrival",  # Corrected: Use expected_arrival
            "expected_departure",# Corrected: Use expected_departure
            "arrival",           # Added: To get actual check-in if available
            "departure",         # Added: To get actual check-out if available
            "customer_id",       # Corrected: Use customer_id
            "actual_room_id",    # Room ID
            "actual_room_rate",  # Room Price
        ],
        # REMOVED: as_dict=True - no longer needed in Frappe v15+
    )

    result_list = []
    for res in reservations:
        # Map fields to 'Extend Reservation Item' doctype
        # Prefer actual arrival/departure dates if they exist, otherwise use expected dates
        display_check_in = res.arrival if res.arrival else res.expected_arrival
        display_check_out = res.departure if res.departure else res.expected_departure

        result_list.append({
            "reservation": res.name,
            "current_check_in": display_check_in,
            "current_check_out": display_check_out,
            "customer": res.customer_id, # Corrected: Map customer_id from Inn Reservation to customer in Extend Reservation Item
            "room": res.actual_room_id,
            "room_price": res.actual_room_rate,
        })
    
    # Optionally, you can add a msgprint here if the populate button should give feedback
    if not result_list:
        frappe.msgprint(_("No reservations found matching the filters."), title=_("No Results"), indicator='blue')
    else:
        frappe.msgprint(_("{0} reservations found.").format(len(result_list)), title=_("Population Complete"), indicator='green')

    return result_list