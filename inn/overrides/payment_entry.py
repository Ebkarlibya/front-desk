# /apps/inn/inn/overrides/payment_entry.py
# -*- coding: utf-8 -*-
# Copyright (c) 2020, Core Initiative and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, cstr

from inn.services.payment_entry_service import PaymentEntryService


# ---------------------------------------------------------------------
# Helper: determine canonical Payment Entry amount (safe across versions)
# ---------------------------------------------------------------------
def _get_payment_entry_effective_amount(pe_doc):
    """
    Determine canonical amount of a Payment Entry.
    Preference order:
      1) paid_amount
      2) received_amount
      3) base_received_amount
      4) base_paid_amount
      5) total_allocated_amount (fallback)
      6) 0.0
    """
    return flt(
        getattr(pe_doc, "paid_amount", None)
        or getattr(pe_doc, "received_amount", None)
        or getattr(pe_doc, "base_received_amount", None)
        or getattr(pe_doc, "base_paid_amount", None)
        or getattr(pe_doc, "total_allocated_amount", None)
        or 0.0
    )


# ---------------------------------------------------------------------
# API: used by Payment Entry UI to fetch unpaid ARIs for a customer
# ---------------------------------------------------------------------
@frappe.whitelist()
def get_unpaid_city_ledger_invoices(customer_id):
    """
    Return unpaid AR City Ledger Invoices for a given customer.
    """
    if not customer_id:
        frappe.throw(_("Please select a Customer first."))

    unpaid_invoices = frappe.get_all(
        "AR City Ledger Invoice",
        filters={
            "customer_id": customer_id,
            "status": ("!=", "Paid"),
        },
        fields=["name", "total_amount", "outstanding"],
        order_by="modified desc",
    )

    result = []
    for invoice in unpaid_invoices:
        result.append(
            {
                "reference_doctype": "AR City Ledger Invoice",
                "reference_name": invoice.name,
                "total_amount": flt(invoice.total_amount),
                "outstanding_amount": flt(invoice.outstanding),
                "allocated_amount": 0.0,
            }
        )

    return result


def validate_payment_entry_allocation_balance(doc, method):
    # Make sure that the Paid amount total is the sum of all allocated in the City ledger table + the payment table
    # Loop through the CLI and check if the allocated amount is equal to or lower that the outstanding amount.
    # If it is, then add the allocated amount to the paid amount total.
    # If it is not, then throw an error and do not submit the payment entry.
    # Add the payment to each of the CLI and update the paid amount total.
    # Update status of the CLI to paid if the paid amount total is equal to the total amount.
    payment_entry_service = PaymentEntryService(doc)
    payment_entry_service.validate_allocated_amount()
    payment_entry_service.allocate_city_ledger_invoices()


# ---------------------------------------------------------------------
# Hook: Payment Entry on_submit
# - Validate allocations provided in doc.custom_unpaid_city_ledger_invoice
# - Apply allocations to AR City Ledger Invoice child table and update totals
# ---------------------------------------------------------------------
def on_payment_entry_submit_custom_logic(doc, method):
    """Allocate payment entry to AR City Ledger Invoices using optimized service."""
    payment_entry_service = PaymentEntryService(doc)
    payment_entry_service.allocate_city_ledger_invoices()


# ---------------------------------------------------------------------
# Hook: Payment Entry on_cancel
# - Remove all rows in AR City Ledger Invoice that reference this PE
# - Update totals and status accordingly
# ---------------------------------------------------------------------
def on_payment_entry_cancel_custom_logic(doc, method):
    """
    Called on Payment Entry cancel to rollback allocations created at submit.
    """
    # Try to call centralized remover in ARCI module if exists
    try:
        remover = frappe.get_attr(
            "inn.inn_hotels.doctype.ar_city_ledger_invoice.ar_city_ledger_invoice.remove_payment_entry_links"
        )
        try:
            removed = remover(doc.name)
            # If remover returns a list, optionally log it
            if removed:
                frappe.msgprint(
                    _(
                        "Removed Payment Entry {0} allocations from AR City Ledger Invoices: {1}"
                    ).format(doc.name, ", ".join(removed))
                )
            return
        except Exception:
            # fallback to local removal if centralized function raises
            pass
    except Exception:
        # centralized remover not present, perform local fallback
        pass

    # Local fallback removal:
    try:
        rows = frappe.db.sql(
            """
            SELECT parent, name, payment_amount
            FROM `tabAR City Ledger Invoice Payment Entry`
            WHERE payment_entry_id = %s
        """,
            (doc.name,),
            as_dict=True,
        )

        parents = {}
        for r in rows:
            parents.setdefault(r.parent, []).append(r)

        updated = []
        for parent_name, child_rows in parents.items():
            try:
                arci = frappe.get_doc("AR City Ledger Invoice", parent_name)
                total_removed = flt(sum(flt(r.payment_amount) for r in child_rows))

                # remove rows referencing this payment_entry_id
                remaining_rows = [
                    r
                    for r in (arci.get("ar_city_ledger_invoice_payment_entry") or [])
                    if r.get("payment_entry_id") != doc.name
                ]
                arci.ar_city_ledger_invoice_payment_entry = remaining_rows

                # update totals
                arci.total_paid = flt(arci.total_paid) - total_removed
                if arci.total_paid < 0:
                    arci.total_paid = 0.0

                arci.outstanding = flt(arci.outstanding) + total_removed

                # update status
                if flt(arci.total_paid) < flt(arci.total_amount) - 0.0001:
                    arci.status = "Unpaid"

                arci.save(ignore_permissions=True)
                updated.append(parent_name)
            except Exception as e:
                frappe.log_error(
                    _(
                        "Error while removing PE links from ARCI {0} for PE {1}: {2}"
                    ).format(parent_name, doc.name, cstr(e)),
                    _("ARCI Remove PE Link Error"),
                )

        if updated:
            frappe.msgprint(
                _(
                    "Removed Payment Entry {0} allocations from AR City Ledger Invoices: {1}"
                ).format(doc.name, ", ".join(updated))
            )
    except Exception as e:
        frappe.log_error(
            _(
                "Failed to cleanup AR City Ledger Invoice links for Payment Entry {0}: {1}"
            ).format(doc.name, cstr(e)),
            _("ARCI Cleanup Error"),
        )
