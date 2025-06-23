from __future__ import unicode_literals
import frappe
from frappe import _, msgprint, DoesNotExistError, ValidationError
from frappe.model.document import Document
from frappe.utils import getdate, add_days, date_diff, nowdate

class ExtendReservation(Document):
    def on_submit(self):
        """
        Called when the Extend Reservation document is submitted.
        Performs validation for room availability and then creates new reservations.
        """
        self.validate_room_availability_on_submit()
        self.create_new_reservations_from_table()
        msgprint(_("Extend Reservation submitted successfully and new reservations created."), indicator='green')

    def validate_room_availability_on_submit(self):
        """
        Validates that each room in the 'reservations_to_extend' table is available for the new date period.
        Raises an error if any room is not available based on Inn Room Booking entries.
        """
        if not self.reservations_to_extend:
            frappe.throw(_("No reservations found in the table to process."))

        items_to_check = [] 

        for item in self.reservations_to_extend:
            # Basic validation for required fields in each row
            if not item.room or not item.new_check_in or not item.new_check_out:
                frappe.throw(_("Room, New Check-in Date, and New Check-out Date are required for all reservations in the table."))

            new_check_in_date = getdate(item.new_check_in)
            new_check_out_date = getdate(item.new_check_out)

            # Date logical validation
            if new_check_in_date > new_check_out_date:
                frappe.throw(_("New Check-in Date ({0}) cannot be after New Check-out Date ({1}) for Original Reservation {2}.").format(
                    item.new_check_in, item.new_check_out, item.reservation))
            
            # Ensure new check-in is not before original check-in, or if it is, that it's handled correctly
            # If the goal is strictly "extension", then new_check_in should ideally be >= original_check_in
            # For simplicity, if it's a "new reservation" based on changed data, we treat it as a fresh booking.
            
            items_to_check.append({
                "room_id": item.room,
                "new_check_in": new_check_in_date,
                "new_check_out": new_check_out_date,
                "original_reservation_name": item.reservation 
            })

        # Perform the actual availability check for all collected rooms
        for data in items_to_check:
            # Check for conflicting Inn Room Booking entries
            # A conflict exists if:
            # 1. The booking's 'start' date is on or before the 'new_check_out' date.
            # 2. The booking's 'end' date is on or after the 'new_check_in' date.
            # AND (status is active)
            
            # Combine filters for active bookings and general unavailability
            room_booking_filters = {
                "room_id": data["room_id"],
                "start": ["<=", data["new_check_out"]],
                "end": [">=", data["new_check_in"]],
                "status": ["in", ["Booked", "Stayed"]], # Active reservation statuses
            }

            # Check for general unavailability statuses
            unavailable_room_availability_filters = {
                "room_id": data["room_id"],
                "start": ["<=", data["new_check_out"]],
                "end": [">=", data["new_check_in"]],
                "room_availability": ["in", ["Under Construction", "Office Use", "Out of Order", "House Use", "Room Compliment"]],
            }

            # If the new reservation is truly a *new* separate booking (as per task description),
            # we don't exclude the original reservation's booking from the conflict check.
            # If it was an "actual extension of the same reservation", you'd add:
            # room_booking_filters["reference_name"] = ["!=", data["original_reservation_name"]]
            # unavailable_room_availability_filters["reference_name"] = ["!=", data["original_reservation_name"]]
            
            conflicting_booking = frappe.db.exists("Inn Room Booking", room_booking_filters)
            conflicting_unavailability = frappe.db.exists("Inn Room Booking", unavailable_room_availability_filters)

            if conflicting_booking or conflicting_unavailability:
                frappe.throw(
                    _("Room {0} is not available from {1} to {2} for the new reservation. Conflict found in Inn Room Booking. Please adjust dates or select another room.").format(
                        data["room_id"],
                        data["new_check_in"].strftime("%Y-%m-%d"),
                        data["new_check_out"].strftime("%Y-%m-%d")
                    )
                )

    def create_new_reservations_from_table(self):
        """
        Creates new Inn Reservation documents and corresponding Inn Room Booking entries
        based on the data in the child table.
        """
        newly_created_reservations = []

        for item in self.reservations_to_extend:
            # Process all rows in the table that passed validation in on_submit
            # (No explicit selection checkbox assumed unless added to DocType)
            
            try:
                original_reservation = frappe.get_doc("Inn Reservation", item.reservation)
            except DoesNotExistError:
                msgprint(_("Original Reservation {0} not found for row {1}. Skipping this entry.").format(item.reservation, item.idx), indicator='red')
                continue # Skip to the next item if original reservation is not found

            # Create a new Inn Reservation document
            new_reservation = frappe.new_doc("Inn Reservation")

            # Copy essential fields from the original reservation or from the Extend Reservation Item
            new_reservation.customer_id = item.customer 
            new_reservation.type = original_reservation.type
            new_reservation.group_id = original_reservation.group_id
            new_reservation.channel = original_reservation.channel
            
            new_reservation.expected_arrival = item.new_check_in
            new_reservation.expected_departure = item.new_check_out
            new_reservation.total_night = date_diff(getdate(new_reservation.expected_departure), getdate(new_reservation.expected_arrival))

            new_reservation.room_type = original_reservation.room_type
            new_reservation.bed_type = original_reservation.bed_type
            new_reservation.room_id = original_reservation.room_id # Reserved Room
            new_reservation.actual_room_id = item.room # Actual Room (from table)
            
            new_reservation.room_rate = original_reservation.room_rate
            new_reservation.base_room_rate = original_reservation.base_room_rate
            new_reservation.init_actual_room_rate = original_reservation.init_actual_room_rate
            new_reservation.actual_room_rate = item.room_price # Room price from table
            new_reservation.discount = original_reservation.discount

            new_reservation.adult = original_reservation.adult
            new_reservation.child = original_reservation.child
            new_reservation.extra_bed = original_reservation.extra_bed
            new_reservation.guest_name = original_reservation.guest_name 

            new_reservation.actual_room_rate_tax = original_reservation.actual_room_rate_tax
            new_reservation.actual_breakfast_rate_tax = original_reservation.actual_breakfast_rate_tax

            # Determine initial status for the new reservation
            if getdate(nowdate()) >= getdate(new_reservation.expected_arrival):
                new_reservation.status = "In House"
            else:
                new_reservation.status = "Reserved"

            try:
                new_reservation.insert(ignore_permissions=True) 
                new_reservation.submit() 
                newly_created_reservations.append(new_reservation.name)

                # Create corresponding Inn Room Booking entry for the NEW reservation
                new_room_booking = frappe.new_doc("Inn Room Booking")
                new_room_booking.room_id = item.room
                new_room_booking.start = new_reservation.expected_arrival # Use actual reservation dates
                new_room_booking.end = new_reservation.expected_departure # Use actual reservation dates
                new_room_booking.status = "Booked" # Mark as booked (or Stayed if already In House)
                new_room_booking.room_availability = "Room Sold" 
                new_room_booking.reference_type = "Inn Reservation"
                new_room_booking.reference_name = new_reservation.name
                new_room_booking.note = _("Booking for new reservation {0} (Extended from {1})").format(new_reservation.name, item.reservation)
                new_room_booking.insert(ignore_permissions=True)
                new_room_booking.submit() # Submit the room booking

                # Link the newly created reservation back to the Extend Reservation Item row
                frappe.db.set_value("Extend Reservation Item", item.name, "new_reservation_id", new_reservation.name)
                
                msgprint(_("New Reservation {0} and Room Booking created for original Reservation {1}.").format(new_reservation.name, item.reservation), indicator='green')

            except ValidationError as e:
                msgprint(_("Failed to create new reservation for original {0} due to validation error: {1}").format(item.reservation, e.message), indicator='red')
            except Exception as e:
                msgprint(_("An unexpected error occurred while creating new reservation for original {0}: {1}").format(item.reservation, str(e)), indicator='red')
                frappe.log_error(f"Error creating new reservation for {item.reservation}", str(e))

        # After attempting to create all reservations, reload the current DocType to show updated links
        if newly_created_reservations: # Only reload if at least one reservation was created
            self.reload()


@frappe.whitelist()
def populate_reservations_for_extension(customer_filter=None, date_start_filter=None, date_end_filter=None):
    """
    Fetches eligible Inn Reservations based on provided filters
    and returns them to populate the 'reservations_to_extend' table.
    """
    
    filters = {}
    
    if customer_filter:
        filters["customer_id"] = customer_filter 
    
    if date_start_filter:
        filters["expected_arrival"] = [">=", getdate(date_start_filter)] 
    if date_end_filter:
        if "expected_arrival" in filters:
            filters["expected_arrival"] = ["between", (getdate(date_start_filter), getdate(date_end_filter))] 
        else:
            filters["expected_arrival"] = ["<=", getdate(date_end_filter)] 

    filters["status"] = ["in", ["In House", "Check In"]] 

    reservations = frappe.get_list(
        "Inn Reservation",
        filters=filters,
        fields=[
            "name",              # Reservation ID
            "expected_arrival",  # Original Check-in Date
            "expected_departure",# Original Check-out Date
            "customer_id",       # Customer ID
            "actual_room_id",    # Room ID
            "actual_room_rate",  # Room Price
            "room_type", "bed_type", "channel", "room_rate", "base_room_rate",
            "init_actual_room_rate", "discount", "adult", "child",
            "extra_bed", "actual_room_rate_tax", "actual_breakfast_rate_tax",
            "type", "group_id", "guest_name"
        ],
    )

    result_list = []
    if reservations:
        for res in reservations:
            # Calculate default new_check_in and new_check_out
            default_new_check_in = add_days(res.expected_departure, 1)
            default_new_check_out = add_days(default_new_check_in, 1) # New Check-out is one day after New Check-in

            result_list.append({
                "reservation": res.name,
                "original_check_in": res.expected_arrival,
                "original_check_out": res.expected_departure,
                "customer": res.customer_id, 
                "room": res.actual_room_id,
                "room_price": res.actual_room_rate,
                "new_check_in": default_new_check_in,  # New default calculation
                "new_check_out": default_new_check_out, # New default calculation
            })
    
    if not result_list:
        msgprint(_("No reservations found matching the filters."), title=_("No Results"), indicator='blue')
    else:
        msgprint(_("{0} reservations found.").format(len(result_list)), title=_("Population Complete"), indicator='green')

    return result_list