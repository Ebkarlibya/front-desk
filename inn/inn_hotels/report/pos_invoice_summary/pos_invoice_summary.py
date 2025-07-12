# Copyright (c) 2025, Core Initiative and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    report_summary = get_report_summary(data)

    return columns, data, None, None, report_summary

def get_columns():
    return [
        {"fieldname": "employee_user_id", "label": _("User ID"), "fieldtype": "Data", "width": 180},
        {"fieldname": "employee_name", "label": _("Employee Name"), "fieldtype": "Data", "width": 180},
        {"fieldname": "amount_paid", "label": _("Amount Paid"), "fieldtype": "Currency", "width": 120},
        {"fieldname": "customer_name", "label": _("Customer"), "fieldtype": "Link", "options": "Customer", "width": 200},
        {"fieldname": "invoice_name", "label": _("Invoice"), "fieldtype": "Link", "options": "POS Invoice", "width": 150},
        {"fieldname": "pos_profile", "label": _("POS Profile"), "fieldtype": "Link", "options": "POS Profile", "width": 150},
        {"fieldname": "posting_date", "label": _("Date"), "fieldtype": "Date", "width": 120},
        {"fieldname": "posting_time", "label": _("Time"), "fieldtype": "Time", "width": 100},
    ]

def get_data(filters):
    conditions = get_conditions(filters)
    
    data = []
    
    pos_invoices = frappe.db.sql(
        f"""
        SELECT
            pos.name as invoice_name,
            pos.posting_date,
            pos.posting_time,
            pos.customer,
            pos.pos_profile,
            pos.owner,
            COALESCE((SELECT sum(amount) FROM `tabSales Invoice Payment` WHERE parent = pos.name), 0) as amount_paid_total 
        FROM
            `tabPOS Invoice` pos
        WHERE
            pos.docstatus = 1 AND
            {conditions}
        ORDER BY
            pos.posting_date DESC, pos.posting_time DESC
        """,
        filters,
        as_dict=True
    )

    for invoice in pos_invoices:
        row = {
            "invoice_name": invoice.invoice_name,
            "posting_date": invoice.posting_date,
            "posting_time": invoice.posting_time,
            "customer_name": invoice.customer,
            "pos_profile": invoice.pos_profile,
            "employee_user_id": invoice.owner,
            "employee_name": get_employee_full_name_from_user(invoice.owner),
            "amount_paid": invoice.amount_paid_total,
        }
        data.append(row)
    
    return data

def get_conditions(filters):
    conditions = []
    if filters.get("customer_name"):
        conditions.append("pos.customer = %(customer_name)s")
    if filters.get("invoice_number"):
        conditions.append("pos.name = %(invoice_number)s")
    if filters.get("from_date"):
        conditions.append("pos.posting_date >= %(from_date)s")
    if filters.get("to_date"):
        conditions.append("pos.posting_date <= %(to_date)s")
    if filters.get("payment_method"):
        conditions.append(
            """ pos.name IN (
                    SELECT parent 
                    FROM `tabSales Invoice Payment` 
                    WHERE mode_of_payment = %(payment_method)s
                )
            """
        )

    if filters.get("invoice_creator"):
        conditions.append("pos.owner = %(invoice_creator)s")
    return " AND ".join(conditions) if conditions else "1=1"


def get_employee_full_name_from_user(user_identifier):
    """
    Retrieves the full name of the employee linked to the user,
    or the full name of the user if no employee is linked.

    """
    employee_data = frappe.db.get_value(
        "Employee",
        {"user_id": user_identifier},
        "employee_name",
        as_dict=True
    )
    if employee_data and employee_data.get("employee_name"):
        return employee_data.get("employee_name")
    user_full_name = None
    user_info = frappe.db.get_value(
        "User", user_identifier, ["full_name"], as_dict=True
    )
    if not user_info and "@" in str(user_identifier):
        user_info = frappe.db.get_value(
            "User", {"email": user_identifier}, ["full_name"], as_dict=True
        )
    if user_info and user_info.get("full_name"):
        user_full_name = user_info.get("full_name")
    return user_full_name if user_full_name else user_identifier

def get_report_summary(data):
    total_amount_paid = sum(row.get("amount_paid", 0) for row in data)
    
    return [
        {
            "value": total_amount_paid,
            "label": _("Total Amount Paid"),
            "datatype": "Currency",
            "indicator": "blue",
            "fieldname": "total_amount_paid_summary"
        }
    ]