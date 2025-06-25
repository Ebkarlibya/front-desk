from __future__ import unicode_literals
import frappe
from frappe import _, msgprint, DoesNotExistError, ValidationError
from frappe.model.document import Document
from frappe.utils import getdate, add_days, date_diff

class ExtendReservation(Document):
    def on_submit(self):
        """
        Called when the Extend Reservation document is submitted.
        Performs validation for extension logic and room availability,
        then creates new reservations and associated folios/bookings.
        """
        self.validate_extension_logic_on_submit()
        self.validate_room_availability_on_submit()
        self.create_new_reservations_from_table()
        msgprint(_("Extend Reservation submitted successfully and new reservations created."), indicator='green')

    def validate_extension_logic_on_submit(self):
        """
        Performs logical validation specific to extension rules,
        like ensuring new check-in is not before original check-in.
        """
        if not self.reservations_to_extend:
            frappe.throw(_("No reservations found in the table to process."))
        
        for item in self.reservations_to_extend:
            new_check_in_date = getdate(item.new_check_in)
            new_check_out_date = getdate(item.new_check_out)

            # Basic field validation
            if not item.new_room or not item.new_room_price or not item.new_check_in or not item.new_check_out:
                frappe.throw(_("New Room, New Room Price, New Check-in Date, and New Check-out Date are required for all reservations in the table."))

            # Date logical validation: New Check-in must be before New Check-out
            if new_check_in_date > new_check_out_date:
                frappe.throw(_("New Check-in Date ({0}) cannot be after New Check-out Date ({1}) for Original Reservation {2}.").format(
                    item.new_check_in, item.new_check_out, item.reservation))

            # **NEW VALIDATION:** Ensure new check-in is not before the original reservation's check-in
            try:
                original_reservation = frappe.get_doc("Inn Reservation", item.reservation)
                original_check_in_date = getdate(original_reservation.expected_arrival)
                
                if new_check_in_date < original_check_in_date:
                    frappe.throw(_("New Check-in Date ({0}) for original Reservation {1} cannot be before its Original Check-in Date ({2}).").format(
                        item.new_check_in, item.reservation, original_reservation.expected_arrival
                    ))
            except DoesNotExistError:
                frappe.throw(_("Original Reservation {0} not found for validation.").format(item.reservation))
            except Exception as e:
                frappe.throw(_("Error validating dates for original Reservation {0}: {1}").format(item.reservation, str(e)))


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
            if not item.new_room or not item.new_check_in or not item.new_check_out:
                frappe.throw(_("New Room, New Check-in Date, and New Check-out Date are required for all reservations in the table."))

            new_check_in_date = getdate(item.new_check_in)
            new_check_out_date = getdate(item.new_check_out)
            
            items_to_check.append({
                "room_id": item.new_room,
                "new_check_in": new_check_in_date,
                "new_check_out": new_check_out_date,
                "original_reservation_name": item.reservation 
            })

        for data in items_to_check:
            # Check for conflicting Inn Room Booking entries that overlap with the new dates
            # Statuses like "Booked", "Stayed", "Check In", "In House" mean the room is occupied/reserved.
            conflicting_booking_filters = {
                "room_id": data["room_id"],
                "start": ["<", data["new_check_out"]],
                "end": [">", data["new_check_in"]],
                "status": ["in", ["Booked", "Stayed", "Check In", "In House"]], 
            }

            # Check for general unavailability statuses like "Out of Order", "Under Construction" etc.
            unavailable_room_availability_filters = {
                "room_id": data["room_id"],
                "start": ["<", data["new_check_out"]],
                "end": [">", data["new_check_in"]],
                "room_availability": ["in", ["Under Construction", "Office Use", "Out of Order", "House Use", "Room Compliment"]],
            }
            
            conflicting_booking_entries = frappe.db.get_list("Inn Room Booking", conflicting_booking_filters)
            conflicting_unavailability_entries = frappe.db.get_list("Inn Room Booking", unavailable_room_availability_filters)

            if conflicting_booking_entries or conflicting_unavailability_entries:
                conflict_details = ""
                if conflicting_booking_entries:
                    conflict_details += _("Conflicting Bookings: {0}. ").format(", ".join([c.name for c in conflicting_booking_entries]))
                if conflicting_unavailability_entries:
                    conflict_details += _("Conflicting Unavailability: {0}. ").format(", ".join([c.name for c in conflicting_unavailability_entries]))
                
                frappe.throw(
                    _("Room {0} is not available from {1} to {2} for new reservation (based on original {3}). {4}Please adjust dates or select another room.").format(
                        data["room_id"],
                        data["new_check_in"].strftime("%Y-%m-%d"),
                        data["new_check_out"].strftime("%Y-%m-%d"),
                        data["original_reservation_name"],
                        conflict_details
                    )
                )

    def create_new_reservations_from_table(self):
        """
        Creates new Inn Reservation documents and corresponding Inn Room Booking entries
        based on the data in the child table.
        """
        newly_created_reservations = []

        for item in self.reservations_to_extend:
            try:
                original_reservation = frappe.get_doc("Inn Reservation", item.reservation)
            except DoesNotExistError:
                msgprint(_("Original Reservation {0} not found for row {1}. Skipping this entry.").format(item.reservation, item.idx), indicator='red')
                continue # Skip to the next item if original reservation is not found

            # **NEW LOGIC: Create a new Inn Folio for EACH new reservation**
            new_folio = frappe.new_doc("Inn Folio")
            new_folio.customer_id = item.customer # Use the customer from the extended row
            new_folio.type = "Guest" # Assuming it's a Guest Folio for new reservations
            # You might want to copy other relevant fields from original_reservation or original_folio to the new_folio if needed
            # For example, if you want a custom naming series for folios created by extension:
            # new_folio.naming_series = "EXT-F-"
            try:
                new_folio.insert(ignore_permissions=True)
                new_folio.submit() # Folios need to be submitted to get a final name and move to correct state
                new_folio_id = new_folio.name
            except Exception as e:
                frappe.throw(_("Failed to create new Folio for original Reservation {0}: {1}").format(item.reservation, str(e)))

            # Create a new Inn Reservation document
            new_reservation = frappe.new_doc("Inn Reservation")

            # Copy essential fields from the original reservation
            new_reservation.customer_id = item.customer # Use the potentially changed customer from the Extend Reservation Item
            new_reservation.type = original_reservation.type
            new_reservation.group_id = original_reservation.group_id
            new_reservation.channel = original_reservation.channel
            new_reservation.guest_name = original_reservation.guest_name
            new_reservation.accompanying_guests = original_reservation.accompanying_guests
            
            # Use new dates from the table
            new_reservation.expected_arrival = item.new_check_in
            new_reservation.expected_departure = item.new_check_out
            new_reservation.total_night = date_diff(getdate(new_reservation.expected_departure), getdate(new_reservation.expected_arrival))

            new_reservation.room_type = original_reservation.room_type
            new_reservation.bed_type = original_reservation.bed_type
            new_reservation.room_id = original_reservation.room_id # This should be the room_type, not the actual_room_id
            new_reservation.actual_room_id = item.new_room # This is the NEW actual room selected for the extension
            
            # Use new room price from the table
            new_reservation.room_rate = original_reservation.room_rate # Keep original room_rate doctype
            new_reservation.base_room_rate = original_reservation.base_room_rate
            new_reservation.init_actual_room_rate = original_reservation.init_actual_room_rate
            new_reservation.actual_room_rate = item.new_room_price # Use new_room_price
            new_reservation.discount = original_reservation.discount

            new_reservation.adult = original_reservation.adult
            new_reservation.child = original_reservation.child
            new_reservation.extra_bed = original_reservation.extra_bed

            new_reservation.actual_room_rate_tax = original_reservation.actual_room_rate_tax
            new_reservation.actual_breakfast_rate_tax = original_reservation.actual_breakfast_rate_tax
            
            # **IMPORTANT:** Link the new reservation to the newly created Folio
            new_reservation.folio_id = new_folio_id

            new_reservation.status = "In House"

            try:
                new_reservation.insert(ignore_permissions=True)
                new_reservation.submit()
                newly_created_reservations.append(new_reservation.name)

                # Create corresponding Inn Room Booking entry for the NEW reservation
                new_room_booking = frappe.new_doc("Inn Room Booking")
                new_room_booking.room_id = item.new_room
                new_room_booking.start = new_reservation.expected_arrival
                new_room_booking.end = new_reservation.expected_departure
                new_room_booking.status = "Booked"
                new_room_booking.room_availability = "Room Sold"
                new_room_booking.reference_type = "Inn Reservation"
                new_room_booking.reference_name = new_reservation.name
                new_room_booking.note = _("Booking for new reservation {0} (Extended from {1})").format(new_reservation.name, item.reservation)
                new_room_booking.insert(ignore_permissions=True)
                new_room_booking.submit()
                
                # Link the newly created reservation back to the Extend Reservation Item row
                frappe.db.set_value("Extend Reservation Item", item.name, "new_reservation_id", new_reservation.name)
                
            except ValidationError as e:
                frappe.throw(_("Failed to create new reservation for original {0} due to validation error: {1}").format(item.reservation, e.message))
            except Exception as e:
                frappe.throw(_("An unexpected error occurred while creating new reservation for original {0}: {1}").format(item.reservation, str(e)))


        # After attempting to create all reservations, reload the current DocType to show updated links
        if newly_created_reservations:
            self.reload()


@frappe.whitelist()
def populate_reservations_for_extension(customer_filter=None, date_start_filter=None, date_end_filter=None):
    """
    Fetches eligible Inn Reservations based on provided filters
    and returns them to populate the 'reservations_to_extend' table.
    """
    
    filters = {}
    
    # Use "customer" for Inn Reservation filter if that's the field name. (Based on Inn Folio doctype snippet, customer_id is used)
    # Check your Inn Reservation doctype for the actual customer field name. Let's assume it's 'customer'.
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
            "name",
            "expected_arrival",
            "expected_departure",
            "customer_id",
            "actual_room_id",
            "actual_room_rate",
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
            default_new_check_out = add_days(default_new_check_in, 1)

            result_list.append({
                "reservation": res.name,
                "original_check_in": res.expected_arrival,
                "original_check_out": res.expected_departure,
                "customer": res.customer_id, 
                "room": res.actual_room_id,
                "new_room": res.actual_room_id,
                "room_price": res.actual_room_rate,
                "new_room_price": res.actual_room_rate,
                "new_check_in": default_new_check_in,
                "new_check_out": default_new_check_out,
            })
    
    if not result_list:
        msgprint(_("No reservations found matching the filters."), title=_("No Results"), indicator='blue')
    else:
        msgprint(_("{0} reservations found.").format(len(result_list)), title=_("Population Complete"), indicator='green')

    return result_list