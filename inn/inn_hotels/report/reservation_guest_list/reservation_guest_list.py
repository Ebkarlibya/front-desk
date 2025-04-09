# Copyright (c) 2025, Core Initiative and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    # إضافة الأعمدة الجديدة مع الأعمدة الحالية
    return [
        {"fieldname": "room", "label": _("Room"), "fieldtype": "Link", "options": "Inn Room", "width": 120},
        {"fieldname": "reservation", "label": _("Reservation"), "fieldtype": "Link", "options": "Inn Reservation", "width": 120},
        {"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Inn Customer", "width": 200},
        # الأعمدة الجديدة في الصف الأب:
        {"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 100},
        {"fieldname": "type", "label": _("Type"), "fieldtype": "Data", "width": 100},
        {"fieldname": "expected_arrival", "label": _("Expected Arrival"), "fieldtype": "Date", "width": 110},
        {"fieldname": "expected_departure", "label": _("Expected Departure"), "fieldtype": "Date", "width": 110},
        # الأعمدة الخاصة ببيانات الضيوف (Child rows):
        {"fieldname": "guest_name", "label": _("Guest Name"), "fieldtype": "Data", "width": 150},
        {"fieldname": "passport_number", "label": _("Passport Number"), "fieldtype": "Data", "width": 150},
        {"fieldname": "nationality", "label": _("Nationality"), "fieldtype": "Link", "options": "Country", "width": 100}
    ]

def get_data(filters):
    conditions = []
    filter_params = {}

    # فلتر حسب رقم الحجز إذا تم الإدخال
    if filters.get("reservation"):
        conditions.append("name = %(reservation)s")
        filter_params["reservation"] = filters.get("reservation")
    
    # فلترة بناءً على فترة تاريخ الوصول المتوقع
    if filters.get("from_date") and filters.get("to_date"):
        conditions.append("expected_arrival BETWEEN %(from_date)s AND %(to_date)s")
        filter_params["from_date"] = filters.get("from_date")
        filter_params["to_date"] = filters.get("to_date")
    
    condition_str = " and ".join(conditions) if conditions else "1=1"
    
    # تحديث الاستعلام لإحضار البيانات المطلوبة
    reservations = frappe.db.sql(
        f""" SELECT name, room_id, customer_id, guest_name,
                    status, type, expected_arrival, expected_departure
             FROM `tabInn Reservation`
             WHERE {condition_str}""",
        filter_params,
        as_dict=True
    )

    data = []
    
    for res in reservations:
        # إنشاء صف أب (Parent row) يحتوي على بيانات الحجز بالكامل
        parent_row = {
            "room": res.room_id,
            "reservation": res.name,
            "customer": res.customer_id,
            "status": res.status,
            "type": res.type,
            "expected_arrival": res.expected_arrival,
            "expected_departure": res.expected_departure,
            "guest_name": "",  # لا يظهر بيانات الضيوف هنا في الصف الأب
            "passport_number": "",
            "nationality": "",
            "is_group": 1  # علامة الصف الرئيسي لكي يكون قابل للطي
        }
        data.append(parent_row)
        
        # تحميل مستند الحجز للحصول على بيانات جدول الضيوف المرافقين
        doc = frappe.get_doc("Inn Reservation", res.name)
        
        if doc.accompanying_guests and len(doc.accompanying_guests) > 0:
            # لكل ضيف مرافق يتم إنشاء صف تابع (Child row)
            for guest in doc.accompanying_guests:
                child_row = {
                    "room": "",
                    "reservation": "",
                    "customer": "",
                    "status": "",
                    "type": "",
                    "expected_arrival": "",
                    "expected_departure": "",
                    "guest_name": guest.companions_name,
                    "passport_number": guest.passport_number,
                    "nationality": guest.nationality,
                    "indent": 1  # علامة الصف الفرعي
                }
                data.append(child_row)
        else:
            # في حال عدم وجود سجلات لضيوف مرافقين، يمكن عرض صف فرعي واحد باستخدام قيمة guest_name الأساسية
            child_row = {
                "room": "",
                "reservation": "",
                "customer": "",
                "status": "",
                "type": "",
                "expected_arrival": "",
                "expected_departure": "",
                "guest_name": res.guest_name,
                "passport_number": "",
                "nationality": "",
                "indent": 1  # علامة الصف الفرعي
            }
            data.append(child_row)
            
    return data
