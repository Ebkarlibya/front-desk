# Copyright (c) 2025, Core Initiative and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = []
    totals = {
        "total_amount": 0.0,
        "total_claimed": 0.0,
        "total_received": 0.0,
        "outstanding": 0.0,
        "left_to_claim": 0.0
    }

    customers = get_customers(filters)

    for customer in customers:
        total_amount = get_total_amount(customer)
        total_claimed = get_total_claimed(customer)
        total_received = get_total_received(customer)

        outstanding = total_amount - total_received
        left_to_claim = total_amount - total_claimed - total_received

        data.append({
            "customer": customer,
            "total_amount": total_amount,
            "total_claimed": total_claimed,
            "total_received": total_received,
            "outstanding": outstanding,
            "left_to_claim": left_to_claim
        })

        # Accumulate totals
        totals["total_amount"] += total_amount
        totals["total_claimed"] += total_claimed
        totals["total_received"] += total_received
        totals["outstanding"] += outstanding
        totals["left_to_claim"] += left_to_claim

    # Append totals row
    data.append({
        "customer": _("Total"),
        "total_amount": totals["total_amount"],
        "total_claimed": totals["total_claimed"],
        "total_received": totals["total_received"],
        "outstanding": totals["outstanding"],
        "left_to_claim": totals["left_to_claim"]
    })

    return columns, data

def get_columns():
    return [
        {
            "label": '<i class="fa fa-user" style="color: #3F51B5;"></i> ' + _("Customer"),
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 300
        },
        {
            "label": '<i class="fa fa-money" style="color: #4CAF50;"></i> ' + _("Total Amount"),
            "fieldname": "total_amount",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": '<i class="fa fa-handshake-o" style="color: #FF9800;"></i> ' + _("Total Claimed"),
            "fieldname": "total_claimed",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": '<i class="fa fa-check-circle" style="color: #009688;"></i> ' + _("Total Received"),
            "fieldname": "total_received",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": '<i class="fa fa-exclamation-triangle" style="color: #F44336;"></i> ' + _("Outstanding"),
            "fieldname": "outstanding",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": '<i class="fa fa-clock-o" style="color: #9C27B0;"></i> ' + _("Left to Claim"),
            "fieldname": "left_to_claim",
            "fieldtype": "Currency",
            "width": 150
        },
    ]

def get_customers(filters):
    # Return only selected customer if filter is provided
    if filters.get("customer"):
        return [filters["customer"]]

    customers = set()

    # Collect customers from all relevant Doctypes
    for doctype, field in [
        ("AR City Ledger", "customer_id"),
        ("AR City Ledger Invoice", "customer_id"),
        ("Payment Entry", "party")
    ]:
        rows = frappe.db.sql(f"""
            SELECT DISTINCT {field} FROM `tab{doctype}`
            WHERE docstatus = 1
        """, as_dict=True)
        for row in rows:
            if row.get(field):
                customers.add(row[field])

    return sorted(customers)

def get_total_amount(customer):
    res = frappe.db.sql(f"""
        SELECT SUM(total_amount) FROM `tabAR City Ledger`
        WHERE customer_id = %s
    """, (customer,))
    return flt(res[0][0]) if res else 0.0

def get_total_claimed(customer):
    res = frappe.db.sql(f"""
        SELECT SUM(total_amount) FROM `tabAR City Ledger Invoice`
        WHERE customer_id = %s
    """, (customer,))
    return flt(res[0][0]) if res else 0.0

def get_total_received(customer):
    res = frappe.db.sql(f"""
        SELECT SUM(paid_amount) FROM `tabPayment Entry`
        WHERE party_type = 'Customer' AND party = %s AND docstatus = 1
        AND paid_to IN (
            SELECT name FROM `tabAccount` WHERE account_type IN ('Cash', 'Bank')
        )
    """, (customer,))
    return flt(res[0][0]) if res else 0.0