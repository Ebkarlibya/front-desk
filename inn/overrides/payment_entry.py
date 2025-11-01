import frappe
from frappe import _
from frappe.utils import flt,cstr


@frappe.whitelist()
def get_unpaid_city_ledger_invoices(customer_id):
    """
    Fetches all unpaid AR City Ledger Invoices for a given customer.

    Args:
        customer_id (str): The customer ID for whom to fetch invoices.

    Returns:
        list: A list of dictionaries, each representing an unpaid AR City Ledger Invoice.
    """
    if not customer_id:
        frappe.throw(_("Please select a Customer first."))

    filters = {
        "customer_id": customer_id,
        "status": ("!=", "Paid"),
    }

    unpaid_invoices = frappe.get_list(
        "AR City Ledger Invoice",
        filters=filters,
        fields=[
            "name",
            "total_amount",
            "outstanding",
        ],
    )

    result = []
    for invoice in unpaid_invoices:
        result.append({
            "reference_doctype": "AR City Ledger Invoice",
            "reference_name": invoice.name,
            "total_amount": invoice.total_amount,
            "outstanding_amount": invoice.outstanding,
            "allocated_amount": 0.0,
        })
    
    return result

def on_payment_entry_submit_custom_logic(doc, method):
    """
    DocEvent hook for Payment Entry's on_submit event.
    This function processes custom AR City Ledger Invoice allocations.
    It adds this Payment Entry's details to the 'ar_city_ledger_invoice_payment_entry'
    child table in each relevant AR City Ledger Invoice.
    Includes validation to prevent over-allocation (allocated_amount > outstanding_amount)
    and to ensure total allocated amount exactly equals the Payment Entry's paid_amount.

    Args:
        doc (frappe.model.document.Document): The Payment Entry document being submitted.
        method (str): The name of the hook method (e.g., 'on_submit').
    """
    if not doc.custom_unpaid_city_ledger_invoice:
        return
    sum_of_allocated_amounts = sum(flt(item.allocated_amount) for item in doc.custom_unpaid_city_ledger_invoice)
    main_payment_entry_paid_amount = flt(doc.paid_amount)

    if sum_of_allocated_amounts != main_payment_entry_paid_amount:
        frappe.throw(
            _("Total allocated amount ({0}) must exactly match the Payment Entry's paid amount ({1}). Please adjust allocations.").format(
                sum_of_allocated_amounts,
               main_payment_entry_paid_amount
            ),
            title=_("Allocation Mismatch Error")
        )

    for invoice_item in doc.custom_unpaid_city_ledger_invoice:
        if invoice_item.reference_name: # Only validate if a reference is selected
            if flt(invoice_item.allocated_amount) > flt(invoice_item.outstanding_amount):
                frappe.throw(
                    _("Allocated amount ({0}) for AR City Ledger Invoice '{1}' cannot exceed its outstanding amount ({2}).").format(
                       flt(invoice_item.allocated_amount),
                        invoice_item.reference_name,
                        flt(invoice_item.outstanding_amount)
                    ),
                    title=_("Over-allocation Error")
                )
    
    for invoice_item in doc.custom_unpaid_city_ledger_invoice:
        # Only process items with a positive allocated amount (and a valid reference, already checked)
        if flt(invoice_item.allocated_amount) > 0 and invoice_item.reference_name:
            try:
                # Get the AR City Ledger Invoice document
                arci_doc = frappe.get_doc("AR City Ledger Invoice", invoice_item.reference_name)
                
                # Add a new row to its 'ar_city_ledger_invoice_payment_entry' child table
                new_payment_entry_ref = arci_doc.append("ar_city_ledger_invoice_payment_entry", {})
                new_payment_entry_ref.payment_entry_id = doc.name # Link to current Payment Entry
                new_payment_entry_ref.payment_amount = invoice_item.allocated_amount # Amount allocated from this PE
                # Update AR City Ledger Invoice's total_paid and outstanding fields
                # These fields are often read-only, but we can update them via a hook or directly here
                arci_doc.total_paid = flt(arci_doc.total_paid) + flt(invoice_item.allocated_amount)
                arci_doc.outstanding = flt(arci_doc.outstanding) - flt(invoice_item.allocated_amount)
                arci_doc.save(ignore_permissions=True) # Save the AR City Ledger Invoice silently
                
            except frappe.DoesNotExistError:
                frappe.log_error(
                    _("AR City Ledger Invoice {0} not found for updating from Payment Entry {1}").format(invoice_item.reference_name, doc.name),
                    _("AR City Ledger Update Error")
                )
            except Exception as e:
                frappe.log_error(
                    _("Error updating AR City Ledger Invoice {0} from Payment Entry {1}: {2}").format(invoice_item.reference_name, doc.name, cstr(e)),
                    _("AR City Ledger Update Error")
                )