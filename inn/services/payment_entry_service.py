import frappe
from frappe import _
from frappe.utils import flt


class PaymentEntryService:
    def __init__(self, doc):
        self.doc = doc

    def validate_allocated_amount(self):
        """
        Ensure total allocated (payment table + city ledger table) does not exceed paid amount.
        """
        total_allocated = self._calculate_total_allocated()
        paid_amount = flt(self.doc.paid_amount)

        if total_allocated - paid_amount > 0.0001:
            frappe.throw(
                _("Allocated amount ({0}) cannot exceed the paid amount ({1}).").format(
                    total_allocated, paid_amount
                )
            )

    def _calculate_total_allocated(self):
        """Calculate total allocated amount from all references."""
        total = 0.0

        for row in getattr(self.doc, "references", []) or []:
            total += flt(row.allocated_amount)

        for row in getattr(self.doc, "custom_unpaid_city_ledger_invoice", []) or []:
            total += flt(row.allocated_amount)

        return total

    def validate_city_ledger_allocations(self):
        """Validate city ledger allocations before processing."""
        allocations = getattr(self.doc, "custom_unpaid_city_ledger_invoice", []) or []
        if not allocations:
            return

        # Validate each allocation individually (no total amount restriction)
        for allocation in allocations:
            self._validate_single_allocation(allocation)

    def _validate_single_allocation(self, allocation):
        """Validate a single allocation entry."""
        ref = allocation.get("reference_name")
        amt = flt(allocation.get("allocated_amount") or 0)

        if not ref:
            frappe.throw(_("Allocation must reference an AR City Ledger Invoice."))

        if amt <= 0:
            frappe.throw(
                _("Allocated amount for {0} must be greater than zero.").format(ref)
            )

        outstanding = frappe.db.get_value("AR City Ledger Invoice", ref, "outstanding")
        if outstanding is None:
            frappe.throw(_("AR City Ledger Invoice {0} not found.").format(ref))

        if amt > outstanding + 0.0001:
            frappe.throw(
                _(
                    "Allocated amount ({0}) for '{1}' cannot exceed outstanding ({2})."
                ).format(amt, ref, outstanding)
            )

    def _calculate_capped_allocations(self, allocations):
        """Calculate total allocations capped by outstanding amounts."""
        total = 0.0
        for allocation in allocations:
            ref = allocation.get("reference_name")
            allocated = flt(allocation.get("allocated_amount") or 0)
            if ref and allocated > 0:
                outstanding = (
                    frappe.db.get_value("AR City Ledger Invoice", ref, "outstanding")
                    or 0
                )
                total += min(allocated, outstanding)
        return total

    def allocate_city_ledger_invoices(self):
        """Allocate payments to AR City Ledger Invoices, capping each to outstanding amount."""
        allocations = getattr(self.doc, "custom_unpaid_city_ledger_invoice", []) or []
        if not allocations:
            return

        self.validate_city_ledger_allocations()
        updated_invoices = []

        for allocation in allocations:
            ref = allocation.get("reference_name")
            allocated = flt(allocation.get("allocated_amount") or 0)

            if ref and allocated > 0:
                invoice_updated = self._allocate_to_single_invoice(ref, allocated)
                if invoice_updated:
                    updated_invoices.append(ref)

        if updated_invoices:
            frappe.msgprint(
                _("Allocated payment entry {0} to AR City Ledger Invoices: {1}").format(
                    self.doc.name, ", ".join(updated_invoices)
                )
            )

    def _allocate_to_single_invoice(self, invoice_name, allocated_amount):
        """Allocate payment to a single invoice, capping at outstanding amount."""
        # Get current values
        outstanding = frappe.db.get_value(
            "AR City Ledger Invoice", invoice_name, "outstanding"
        )
        total_paid = frappe.db.get_value(
            "AR City Ledger Invoice", invoice_name, "total_paid"
        )

        if not outstanding or outstanding <= 0:
            return False

        apply_amount = min(allocated_amount, outstanding)

        # Add payment entry row using SQL for efficiency
        frappe.db.sql(
            """
            INSERT INTO `tabAR City Ledger Invoice Payment Entry`
            (name, creation, modified, modified_by, owner, docstatus, parent, parenttype, parentfield,
             payment_entry_id, payment_amount, idx)
            VALUES
            (%s, NOW(), NOW(), %s, %s, 0, %s, 'AR City Ledger Invoice', 'ar_city_ledger_invoice_payment_entry',
             %s, %s, (SELECT COALESCE(MAX(idx), 0) + 1 FROM `tabAR City Ledger Invoice Payment Entry` WHERE parent = %s))
            """,
            (
                frappe.generate_hash("", 10),
                frappe.session.user,
                frappe.session.user,
                invoice_name,
                self.doc.name,
                apply_amount,
                invoice_name,
            ),
        )

        # Update totals using set_value for efficiency
        new_total_paid = flt(total_paid) + apply_amount
        new_outstanding = max(0.0, flt(outstanding) - apply_amount)
        new_status = "Paid" if new_outstanding <= 0.0001 else "Unpaid"

        frappe.db.set_value(
            "AR City Ledger Invoice",
            invoice_name,
            {
                "total_paid": new_total_paid,
                "outstanding": new_outstanding,
                "status": new_status,
            },
        )

        return True
