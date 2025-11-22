# /apps/inn/inn/overrides/payment_entry.py
# -*- coding: utf-8 -*-
# Copyright (c) 2020, Core Initiative and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, cstr

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
        getattr(pe_doc, "paid_amount", None) or
        getattr(pe_doc, "received_amount", None) or
        getattr(pe_doc, "base_received_amount", None) or
        getattr(pe_doc, "base_paid_amount", None) or
        getattr(pe_doc, "total_allocated_amount", None) or
        0.0
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
        result.append({
            "reference_doctype": "AR City Ledger Invoice",
            "reference_name": invoice.name,
            "total_amount": flt(invoice.total_amount),
            "outstanding_amount": flt(invoice.outstanding),
            "allocated_amount": 0.0,
        })

    return result

# ---------------------------------------------------------------------
# Hook: Payment Entry on_submit
# - Validate allocations provided in doc.custom_unpaid_city_ledger_invoice
# - Apply allocations to AR City Ledger Invoice child table and update totals
# ---------------------------------------------------------------------
def on_payment_entry_submit_custom_logic(doc, method):
    """
    Called on Payment Entry on_submit to allocate this Payment Entry to AR City Ledger Invoices.
    Expects `doc.custom_unpaid_city_ledger_invoice` to contain rows with:
      - reference_name (AR City Ledger Invoice)
      - allocated_amount
    """
    allocations = getattr(doc, "custom_unpaid_city_ledger_invoice", None)
    if not allocations:
        return

    # Effective PE amount
    pe_amount = flt(getattr(doc, "paid_amount", None) or 0.0)

    # Sum of allocations provided by user
    sum_allocated = flt(sum(flt(a.allocated_amount) for a in allocations))

    # Validate total matches PE amount (strict equality expected by your spec)
    if abs(sum_allocated - pe_amount) > 0.0001:
        frappe.throw(
            _("Total allocated amount ({0}) must exactly match the Payment Entry's amount ({1}).").format(
                sum_allocated, pe_amount
            ),
            title=_("Allocation Mismatch Error")
        )

    # Validate each allocation against the invoice outstanding and system state
    for a in allocations:
        ref = a.get("reference_name")
        amt = flt(a.get("allocated_amount") or 0)
        if not ref:
            frappe.throw(_("Allocation must reference an AR City Ledger Invoice."))
        if amt <= 0:
            frappe.throw(_("Allocated amount for {0} must be greater than zero.").format(ref))

        try:
            arci = frappe.get_doc("AR City Ledger Invoice", ref)
        except frappe.DoesNotExistError:
            frappe.throw(_("AR City Ledger Invoice {0} not found.").format(ref))

        if flt(amt) > flt(arci.outstanding):
            frappe.throw(
                _("Allocated amount ({0}) for AR City Ledger Invoice '{1}' cannot exceed its outstanding amount ({2}).").format(
                    amt, ref, flt(arci.outstanding)
                ),
                title=_("Over-allocation Error")
            )

    # Prevent double allocation: check existing DB-linked allocations for this PE
    total_already_linked = flt(frappe.db.sql(
        """SELECT COALESCE(SUM(payment_amount), 0)
           FROM `tabAR City Ledger Invoice Payment Entry`
           WHERE payment_entry_id = %s""",
        (doc.name,)
    )[0][0])

    # If there are existing DB links and they conflict with new allocations, refuse
    if total_already_linked:
        # Typically should be zero before submit; but guard anyway
        if abs(total_already_linked - sum_allocated) > 0.0001:
            frappe.throw(
                _("This Payment Entry already has existing allocations ({0}). Please reconcile before submitting new allocations.").format(total_already_linked),
                title=_("Existing Allocation Conflict")
            )

    # All validations passed -> apply allocations
    updated_invoices = []
    for a in allocations:
        ref = a.get("reference_name")
        amt = flt(a.get("allocated_amount") or 0)
        if not ref or amt <= 0:
            continue

        try:
            arci = frappe.get_doc("AR City Ledger Invoice", ref)

            # Protect against duplicate rows for same PE in same ARCI
            existing_for_pe = flt(sum(flt(r.payment_amount or 0) for r in (arci.get("ar_city_ledger_invoice_payment_entry") or []) if r.get("payment_entry_id") == doc.name))
            if existing_for_pe:
                # if it already exists, ensure we are not over-allocating beyond PE effective amount
                if existing_for_pe + amt - pe_amount > 0.0001:
                    frappe.throw(
                        _("Allocating {0} to AR City Ledger Invoice {1} would exceed Payment Entry {2} remaining amount.").format(
                            amt, ref, doc.name
                        ),
                        title=_("Allocation Overrun")
                    )

            # Append new child row linking to Payment Entry
            new_row = arci.append("ar_city_ledger_invoice_payment_entry", {})
            new_row.payment_entry_id = doc.name
            new_row.payment_amount = amt

            # Update totals
            arci.total_paid = flt(arci.total_paid) + amt
            arci.outstanding = flt(arci.outstanding) - amt
            if arci.outstanding < 0:
                arci.outstanding = 0.0

            # Update status
            if flt(arci.total_paid) >= flt(arci.total_amount) - 0.0001:
                arci.status = "Paid"
            else:
                arci.status = "Unpaid"

            arci.save(ignore_permissions=True)
            updated_invoices.append(ref)

        except Exception as e:
            frappe.log_error(
                _("Error updating AR City Ledger Invoice {0} from Payment Entry {1}: {2}").format(ref, doc.name, cstr(e)),
                _("AR City Ledger Update Error")
            )
            # Raise to notify caller (so submission will fail)
            frappe.throw(_("Failed to allocate Payment Entry {0} to AR City Ledger Invoice {1}: {2}").format(doc.name, ref, cstr(e)))

    # optionally inform user
    frappe.msgprint(_("Allocated Payment Entry {0} to AR City Ledger Invoices: {1}").format(doc.name, ", ".join(updated_invoices)))

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
        remover = frappe.get_attr("inn.inn_hotels.doctype.ar_city_ledger_invoice.ar_city_ledger_invoice.remove_payment_entry_links")
        try:
            removed = remover(doc.name)
            # If remover returns a list, optionally log it
            if removed:
                frappe.msgprint(_("Removed Payment Entry {0} allocations from AR City Ledger Invoices: {1}").format(doc.name, ", ".join(removed)))
            return
        except Exception:
            # fallback to local removal if centralized function raises
            pass
    except Exception:
        # centralized remover not present, perform local fallback
        pass

    # Local fallback removal:
    try:
        rows = frappe.db.sql("""
            SELECT parent, name, payment_amount
            FROM `tabAR City Ledger Invoice Payment Entry`
            WHERE payment_entry_id = %s
        """, (doc.name,), as_dict=True)

        parents = {}
        for r in rows:
            parents.setdefault(r.parent, []).append(r)

        updated = []
        for parent_name, child_rows in parents.items():
            try:
                arci = frappe.get_doc("AR City Ledger Invoice", parent_name)
                total_removed = flt(sum(flt(r.payment_amount) for r in child_rows))

                # remove rows referencing this payment_entry_id
                remaining_rows = [r for r in (arci.get("ar_city_ledger_invoice_payment_entry") or []) if r.get("payment_entry_id") != doc.name]
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
                    _("Error while removing PE links from ARCI {0} for PE {1}: {2}").format(parent_name, doc.name, cstr(e)),
                    _("ARCI Remove PE Link Error")
                )

        if updated:
            frappe.msgprint(_("Removed Payment Entry {0} allocations from AR City Ledger Invoices: {1}").format(doc.name, ", ".join(updated)))
    except Exception as e:
        frappe.log_error(_("Failed to cleanup AR City Ledger Invoice links for Payment Entry {0}: {1}").format(doc.name, cstr(e)), _("ARCI Cleanup Error"))