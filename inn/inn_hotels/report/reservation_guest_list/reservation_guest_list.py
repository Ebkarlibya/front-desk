# Copyright (c) 2025, Core Initiative and contributors
# For license information, please see license.txt

from collections import defaultdict
import frappe
from frappe import _


def execute(filters=None):
    """Execute the report and return columns and data."""
    columns = get_columns()
    data = get_data(filters)
    report_summary = get_report_summary(data["rooms_booked"], data["guests_booked"])
    return columns, data["data"], None, None, report_summary


def get_columns():
    """Return columns for the report."""
    return [
        {
            "fieldname": "room",
            "label": _("Room"),
            "fieldtype": "Link",
            "options": "Inn Room",
            "width": 120,
        },
        {
            "fieldname": "reservation",
            "label": _("Reservation"),
            "fieldtype": "Link",
            "options": "Inn Reservation",
            "width": 120,
        },
        {
            "fieldname": "customer",
            "label": _("Customer"),
            "fieldtype": "Link",
            "options": "Inn Customer",
            "width": 200,
        },
        {
            "fieldname": "status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 100,
        },
        {"fieldname": "type", "label": _("Type"), "fieldtype": "Data", "width": 200},
        {
            "fieldname": "expected_arrival",
            "label": _("Expected Arrival"),
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "fieldname": "expected_departure",
            "label": _("Expected Departure"),
            "fieldtype": "Date",
            "width": 110,
        },
        # الأعمدة الخاصة ببيانات الضيوف (Child rows):
        {
            "fieldname": "guest_name",
            "label": _("Guest Name"),
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "fieldname": "passport_number",
            "label": _("Passport Number"),
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "fieldname": "nationality",
            "label": _("Nationality"),
            "fieldtype": "Link",
            "options": "Country",
            "width": 100,
        },
    ]


def get_report_summary(rooms_booked, guests_booked):
    """
    Generate a summary for the report.

    Args:
        rooms_booked (int): Total number of rooms booked.
        guests_booked (int): Total number of guests booked.

    Returns:
        list: A list containing the summary data.
    """
    return [
        {"label": _("Total Rooms Booked"), "value": rooms_booked, "indicator": "Red"},
        {
            "label": _("Total Guests Booked"),
            "value": guests_booked,
            "indicator": "Green",
        },
    ]


def get_data(filters):
    """
    Retrieves and structures reservation and guest data for the reservation guest list report.

    Args:
        filters (dict): A dictionary of filters to apply to the reservation query. Supported keys:
            - "reservation": (str) Reservation name to filter by.
            - "from_date": (str) Start date for expected arrival (inclusive).
            - "to_date": (str) End date for expected arrival (inclusive).
            - "include_cancelled": (bool) Whether to include cancelled reservations.

    Returns:
        list[dict]: A list of dictionaries representing reservations and their guests, structured in a tree format.
            Each dictionary contains reservation and guest details, with an "indent" key indicating hierarchy:
                - indent = 0: Main guest (reservation holder).
                - indent = 1: Accompanying guest.
            For accompanying guests, reservation-related fields are cleared.
    """
    conditions = []
    filter_params = {}
    if filters.get("reservation"):
        conditions.append("name = %(reservation)s")
        filter_params["reservation"] = filters.get("reservation")
    if filters.get("from_date") and filters.get("to_date"):
        conditions.append("expected_arrival BETWEEN %(from_date)s AND %(to_date)s")
        filter_params["from_date"] = filters.get("from_date")
        filter_params["to_date"] = filters.get("to_date")
    if filters.get("include_cancelled"):
        conditions.append("status NOT IN ('Draft')")
    else:
        conditions.append("status NOT IN ('Cancel', 'Draft')")
    condition_str = " AND ".join(conditions) if conditions else "1=1"

    reservations = frappe.db.sql(
        f"""
            SELECT
                res.name AS reservation,
                res.guest_name AS main_guest,
                res.customer_id AS customer,
                res.arrival AS expected_arrival,
                res.departure AS expected_departure,
                res.room_id AS room,
                res.status,
                res.type,
                ag.name AS guest_id,
                ag.companions_name AS guest_name,
                ag.passport_number,
                ag.nationality,
                ag.idx AS idx
            FROM `tabInn Reservation` res
            LEFT JOIN `tabAccompanying guests` ag ON ag.parent = res.name
            WHERE {condition_str}
            ORDER BY res.name, ag.idx
        """,
        filter_params,
        as_dict=True,
        debug=1,
    )

    tree_data = []
    reservations_grouped = defaultdict(list)

    rooms_booked = 0
    guests_booked = 0

    # Step 1: Group by reservation
    for row in reservations:
        reservations_grouped[row["reservation"]].append(row)

    for res in reservations_grouped.items():
        rooms_booked += 1
        guests_booked += len(res[1])

    # Step 2: Build tree structure
    for _res_name, guests in reservations_grouped.items():
        main_guest_name = guests[0]["main_guest"]

        # Case: No main guest defined — take first accompanying guest
        if not main_guest_name:
            for i, guest in enumerate(guests):
                guest["indent"] = 0 if i == 0 else 1
                if guest["indent"] == 1:
                    guest["reservation"] = ""  # Clear reservation for sub-guests
                    guest["room"] = ""  # Clear room for sub-guests
                    guest["customer"] = ""  # Clear customer for sub-guests
                    guest["status"] = ""
                    guest["type"] = ""
                    guest["expected_arrival"] = ""
                    guest["expected_departure"] = ""
                tree_data.append(guest)

        else:
            found_main = False
            for guest in guests:
                if guest["guest_name"] == main_guest_name and not found_main:
                    guest["indent"] = 0
                    found_main = True
                else:
                    guest["indent"] = 1
                    guest["reservation"] = ""  # Clear reservation for sub-guests
                    guest["room"] = ""  # Clear room for sub-guests
                    guest["customer"] = ""  # Clear customer for sub-guests
                    guest["status"] = ""
                    guest["type"] = ""
                    guest["expected_arrival"] = ""
                    guest["expected_departure"] = ""
                tree_data.append(guest)

    tree_data.append(
        {
            "reservation": "",
            "main_guest": "",
            "customer": "",
            "expected_arrival": "",
            "expected_departure": "",
            "room": "",
            "status": "",
            "type": "Total Rooms Booked",
            "guest_id": "",
            "guest_name": f"{rooms_booked}",
            "passport_number": "",
            "nationality": "",
            "indent": 0,
        }
    )

    tree_data.append(
        {
            "reservation": "",
            "main_guest": "",
            "customer": "",
            "expected_arrival": "",
            "expected_departure": "",
            "room": "",
            "status": "",
            "type": "Total Guests Booked",
            "guest_id": "",
            "guest_name": f"{guests_booked}",
            "passport_number": "",
            "nationality": "",
            "indent": 0,
        }
    )
    return {
        "data": tree_data,
        "rooms_booked": rooms_booked,
        "guests_booked": guests_booked,
    }
    # return tree_data
