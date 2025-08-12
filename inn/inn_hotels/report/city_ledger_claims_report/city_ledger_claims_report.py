# Copyright (c) 2025, Core Initiative
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    """Main report execution function."""
    if not filters:
        filters = {}

    columns = get_columns()
    data = []

    # Initialize totals
    totals = {
        "total_amount": 0.0,
        "total_claimed": 0.0,
        "total_received": 0.0,
        "outstanding": 0.0,
        "left_to_claim": 0.0
    }

    # Get all customers even if they exist in only one source
    customers = get_all_customers(filters)

    for customer in customers:
        # Fetch amounts from each table
        total_amount = get_total_amount(customer)
        total_claimed = get_total_claimed(customer)
        total_received = get_total_received(customer)

        # Compute derived values
        outstanding = total_amount - total_received
        left_to_claim = total_amount - total_claimed - total_received

        # Append row to report
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

    # Add totals row
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
    """Define the columns of the report."""
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


def get_all_customers(filters):
    """
    Get all unique customers from AR City Ledger, Invoice, and Payment Entry.
    Include all even if customer exists in only one table.
    """
    if filters.get("customer"):
        return [filters["customer"]]

    customer_set = set()

    # Get customers from AR City Ledger
    ar_customers = frappe.db.sql("""
        SELECT DISTINCT customer_id FROM `tabAR City Ledger`
        WHERE customer_id IS NOT NULL AND customer_id != ''
    """, as_dict=True)
    customer_set.update([row.customer_id for row in ar_customers])

    # Get customers from AR City Ledger Invoice
    invoice_customers = frappe.db.sql("""
        SELECT DISTINCT customer_id FROM `tabAR City Ledger Invoice`
        WHERE customer_id IS NOT NULL AND customer_id != ''
    """, as_dict=True)
    customer_set.update([row.customer_id for row in invoice_customers])

    # Get customers from Payment Entry
    payment_customers = frappe.db.sql("""
        SELECT DISTINCT party FROM `tabPayment Entry`
        WHERE docstatus = 1 AND party_type = 'Customer' AND party IS NOT NULL AND party != ''
    """, as_dict=True)
    customer_set.update([row.party for row in payment_customers])

    return sorted(customer_set)


def get_total_amount(customer):
    """Get total amount from AR City Ledger."""
    res = frappe.db.sql("""
        SELECT SUM(total_amount) FROM `tabAR City Ledger`
        WHERE customer_id = %s
    """, (customer,))
    return flt(res[0][0]) if res else 0.0


def get_total_claimed(customer):
    """Get total claimed from AR City Ledger Invoice."""
    res = frappe.db.sql("""
        SELECT SUM(total_amount) FROM `tabAR City Ledger Invoice`
        WHERE customer_id = %s
    """, (customer,))
    return flt(res[0][0]) if res else 0.0


def get_total_received(customer):
    """Get total received from Payment Entry (Cash/Bank)."""
    res = frappe.db.sql("""
        SELECT SUM(paid_amount) FROM `tabPayment Entry`
        WHERE party_type = 'Customer' AND party = %s AND docstatus = 1
        AND paid_to IN (
            SELECT name FROM `tabAccount` WHERE account_type IN ('Cash', 'Bank')
        )
    """, (customer,))
    return flt(res[0][0]) if res else 0.0