# Copyright (c) 2025, Core Initiative and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
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
        {"fieldname": "type", "label": _("Type"), "fieldtype": "Data", "width": 100},
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


def get_data(filters):
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
    from collections import defaultdict

    tree_data = []
    reservations_grouped = defaultdict(list)

    # Step 1: Group by reservation
    for row in reservations:
        reservations_grouped[row["reservation"]].append(row)

    # Step 2: Build tree structure
    for res_name, guests in reservations_grouped.items():
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
    return tree_data

    #         "status": res.status,
    #         "type": res.type,
    #         "expected_arrival": res.expected_arrival,
    #         "expected_departure": res.expected_departure,
    #         "guest_name": "",
    #         "passport_number": "",
    #         "nationality": "",
    #         "is_group": 1,  # علامة الصف الرئيسي لكي يكون قابل للطي
    #     }
    #     data.append(parent_row)

    #     # تحميل مستند الحجز للحصول على بيانات جدول الضيوف المرافقين
    #     doc = frappe.get_all("Accompanying guests", filters={"parent": res.name})

    #     existing_accompanying_guest_names = []
    #     if doc.accompanying_guests:
    #         existing_accompanying_guest_names = [
    #             guest.companions_name for guest in doc.accompanying_guests
    #         ]

    #     if res.guest_name and res.guest_name not in existing_accompanying_guest_names:
    #         main_guest_row = {
    #             "room": "",
    #             "reservation": "",
    #             "customer": "",
    #             "status": "",
    #             "type": "",
    #             "expected_arrival": "",
    #             "expected_departure": "",
    #             "guest_name": res.guest_name,
    #             "passport_number": "",
    #             "nationality": "",
    #             "indent": 1,
    #         }
    #         data.append(main_guest_row)
    #     if doc.accompanying_guests and len(doc.accompanying_guests) > 0:
    #         for guest in doc.accompanying_guests:
    #             child_row_accompanying = {
    #                 "room": "",
    #                 "reservation": "",
    #                 "customer": "",
    #                 "status": "",
    #                 "type": "",
    #                 "expected_arrival": "",
    #                 "expected_departure": "",
    #                 "guest_name": guest.companions_name,
    #                 "passport_number": guest.passport_number,
    #                 "nationality": guest.nationality,
    #                 "indent": 1,  # علامة الصف الفرعي
    #             }
    #             data.append(child_row_accompanying)
