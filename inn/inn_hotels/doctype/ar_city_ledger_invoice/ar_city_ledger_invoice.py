# -*- coding: utf-8 -*-
# Copyright (c) 2020, Core Initiative and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt,cstr

class ARCityLedgerInvoice(Document):
    def validate(self):
        """
        Validates the 'AR City Ledger Invoice' document before saving.
        This includes checking for:
        1. Duplicate folios within the same document's child table.
        2. Folios already present in other submitted AR City Ledger Invoices.
        """
        self.validate_unique_folios_in_table()
        self.validate_folios_not_in_other_invoices()
        self.validate_payment_totals_not_exceed()
    def validate_unique_folios_in_table(self):
        """
        Checks if there are any duplicate folios in the 'folio' child table
        of the current AR City Ledger Invoice document.
        Raises a ValidationError if duplicates are found.
        """
        if not self.folio:
            return 

        seen_folios = set()
        for item in self.folio:
            if not item.folio_id:
                continue 
            
            if item.folio_id in seen_folios:
                frappe.throw(
                    _("Folio '{0}' is duplicated in the Folio to be Collected table. Please ensure each folio is added only once.").format(item.folio_id),
                    title=_("Duplicate Folio Error")
                )
            seen_folios.add(item.folio_id)

    def validate_folios_not_in_other_invoices(self):
        """
        Checks if any folio in the 'folio' child table of the current document
        is already present in another AR City Ledger Invoice that is not cancelled.
        Raises a ValidationError if a folio is found in another invoice.
        """
        if not self.folio:
            return 

        current_document_name = self.name if self.name else "" 


        for item in self.folio:
            if not item.folio_id:
                continue

            try:
                conflicting_invoice_name = frappe.db.sql(
                    """
                    SELECT
                        t1.name
                    FROM
                        `tabAR City Ledger Invoice` t1
                    JOIN
                        `tabAR City Ledger Invoice Folio` t2
                        ON t1.name = t2.parent
                    WHERE
                        t2.folio_id = %(folio_id)s
                        AND t1.name != %(current_doc_name)s
                        AND t1.status != 'Cancelled'
                    LIMIT 1
                    """,
                    {
                        "folio_id": item.folio_id,
                        "current_doc_name": current_document_name
                    },
                    as_dict=True
                )

            except Exception as e:
                frappe.throw(_("An unexpected error occurred during folio validation for {0}: {1}").format(item.folio_id, str(e)))

            if conflicting_invoice_name:
                conflicting_invoice_name = conflicting_invoice_name[0].name
                frappe.throw(
                    _("Folio '{0}' is already present in another AR City Ledger Invoice '{1}'. Please remove it from this document or cancel the conflicting invoice.").format(item.folio_id, conflicting_invoice_name),
                    title=_("Folio Already Used Error")
                )
    def validate_payment_totals_not_exceed(self):
        """
        Ensure sum(payments.payment_amount) + sum(payment_entry.payment_amount)
        does not exceed total amount from folios.
        """
        # حساب إجمالي الفوليوهات
        total_amount = 0.0
        if getattr(self, "folio", None):
            for f in self.folio:
                if getattr(f, "amount", None):
                    total_amount += flt(f.amount)

        # حساب إجمالي الدفعات من جدول payments
        total_paid = 0.0
        if getattr(self, "payments", None):
            for p in self.payments:
                total_paid += flt(p.get("payment_amount", 0))

        # حساب إجمالي الدفعات من جدول Payment Entry (اسم الحقل حسب DocType)
        if getattr(self, "ar_city_ledger_invoice_payment_entry", None):
            for pe in self.ar_city_ledger_invoice_payment_entry:
                total_paid += flt(pe.get("payment_amount", 0))

        # تحقق الفائض
        if flt(total_paid) > flt(total_amount):
            frappe.throw(
                _("Total payments ({0}) exceed Total amount ({1}). Please correct payments so Outstanding is not negative.").format(
                    total_paid, total_amount
                ),
                title=_("Overpayment Error")
            )
@frappe.whitelist()
def get_payments_accounts(mode_of_payment):
    hotel_settings = frappe.get_single("Inn Hotels Setting")
    account = frappe.db.get_value(
        "Mode of Payment Account",
        {
            "parent": mode_of_payment,
            "company": frappe.get_doc("Global Defaults").default_company,
        },
        "default_account",
    )
    against = frappe.db.get_list(
        "Account",
        filters={"name": hotel_settings.ar_city_ledger_invoice_payment_account},
    )[0].name
    return account, against


@frappe.whitelist()
def make_payment(id):
    """
    Processes payments for an AR City Ledger Invoice.
    Creates and submits Journal Entries for unpaid payments.
    Updates payment status and stores Journal Entry ID if total amounts match.
    Conditionally sets Party Type and Party based on account type.

    Args:
        id (str): The name of the AR City Ledger Invoice document.

    Returns:
        int: 1 if payments are successfully processed and invoice status updated,
             0 if payment processing fails due to validation.
    """
    doc = frappe.get_doc("AR City Ledger Invoice", id)
    
    if not doc.folio or len(doc.folio) == 0:
        frappe.throw(_("Please add Folio(s) to be Collected first before making payment."))

    # current_total_amount_from_folios = sum(flt(f.amount) for f in doc.folio if f.amount is not None)
    unpaid_payments = list(filter(lambda p: flt(p.get("paid")) == 0, doc.get("payments")))
    
    # Check if there are any payments to process
    if not unpaid_payments:
        frappe.throw(_("No unpaid payments found to process."))

    return_status = 1

    for payment_row in unpaid_payments:
        remark = _("AR City Ledger Invoice Payments: {0}").format(cstr(payment_row.name))
        doc_je = frappe.new_doc("Journal Entry")
        doc_je.title = cstr(payment_row.name)
        doc_je.voucher_type = "Journal Entry"
        doc_je.naming_series = "ACC-JV-.YYYY.-"
        doc_je.posting_date = payment_row.payment_reference_date
        doc_je.company = frappe.get_doc("Global Defaults").default_company
        doc_je.total_amount_currency = frappe.get_doc("Global Defaults").default_currency
        doc_je.remark = remark
        doc_je.user_remark = remark

        # Debit Account (Mode of Payment's default account)
        doc_jea_debit = frappe.new_doc("Journal Entry Account")
        doc_jea_debit.account = payment_row.account
        doc_jea_debit.debit = payment_row.payment_amount
        doc_jea_debit.debit_in_account_currency = payment_row.payment_amount
        # doc_jea_debit.party_type = "Customer"
        # doc_jea_debit.party = doc.customer_id
        doc_jea_debit.user_remark = remark

        # Credit Account (AR City Ledger Payment Account from settings)
        doc_jea_credit = frappe.new_doc("Journal Entry Account")
        doc_jea_credit.account = payment_row.account_against
        doc_jea_credit.credit = payment_row.payment_amount
        doc_jea_credit.credit_in_account_currency = payment_row.payment_amount
        doc_jea_credit.party_type = "Customer"
        doc_jea_credit.party = doc.customer_id
        doc_jea_credit.user_remark = remark

        doc_je.append("accounts", doc_jea_debit)
        doc_je.append("accounts", doc_jea_credit)

        try:
            doc_je.save()
            doc_je.submit()
            
            # Update payment status and store Journal Entry ID
            frappe.db.set_value(
                "AR City Ledger Invoice Payments",
                payment_row.name,
                "journal_entry_id",
                doc_je.name,
                update_modified=False 
            )
            frappe.db.set_value(
                "AR City Ledger Invoice Payments",
                payment_row.name,
                "paid", 1,
                update_modified=True 
            )
            frappe.db.commit()

        except Exception as e:
            frappe.db.rollback()
            frappe.log_error(f"Failed to create/submit Journal Entry for payment {payment_row.name}. Error: {str(e)}", "ACL_Payment_Error")
            frappe.throw(_("Failed to process payment {0}: {1}").format(payment_row.name, str(e)))
            return 0

    # Re-fetch doc to get updated totals after payments
    doc.reload() 

    # Check if total_paid now equals total_amount (using reloaded doc values)
    if flt(doc.total_paid) == flt(doc.total_amount):
        doc.status = "Paid"
        doc.save()
        
        # Update associated AR City Ledger documents (if applicable)
        for folio_item in doc.folio:
            ar_city_ledger_doc = frappe.get_doc("AR City Ledger", folio_item.ar_city_ledger_id)
            ar_city_ledger_doc.is_paid = 1
            ar_city_ledger_doc.save(ignore_permissions=True) 

    return return_status


def cancel_ar_city_ledger_invoice(arci_id, jv_id):
    """
    Function to cancel AR City Ledger Invoice
    """
    try:
        arci = frappe.get_doc("AR City Ledger Invoice", arci_id)
        if arci.status == "Cancelled":
            frappe.throw(frappe._("AR City Ledger Invoice is already cancelled."))
        if arci.status == "Paid":
            frappe.throw(
                frappe._(
                    "Cannot cancel a paid AR City Ledger Invoice. Please reverse the payment first."
                )
            )
        jv = frappe.get_doc("Journal Entry", jv_id)
        jv.cancel()

        return True
    except Exception as e: 
        frappe.log_error(f"Error cancelling AR City Ledger Invoice {arci_id} or JE {jv_id}: {str(e)}", "ACL_Cancel_Error")
        return False


def get_arci_details_print(folios):
    folio_list = []
    for folio in folios:
        # folio_doc = frappe.get_doc("Inn Folio", folio["folio_id"])
        transactions = frappe.db.get_all(
            "Inn Folio Transaction",
            filters={"parent": folio.folio_id},
            fields=["name", "amount", "is_void", "transaction_type", "mode_of_payment"],
        )
        folio_list.append(
            {
                "folio_name": folio.folio_id,
                "transactions": transactions,
            }
        )
    return folio_list

@frappe.whitelist()
def get_payment_entry_remaining(payment_entry_id, current_arci=""):
    """
    Return remaining amount for a Payment Entry after excluding allocations recorded
    in AR City Ledger Invoice Payment Entry (optionally excluding current ARCI).
    Response dict:
      { "pe_amount": float,
        "total_allocated_excluding_current": float,
        "remaining": float }
    On error returns {"error": "<message>"}
    """
    if not payment_entry_id:
        return {"error": _("Payment Entry id is required.")}

    # Load full Payment Entry doc (safer across ERPNext versions)
    try:
        pe_doc = frappe.get_doc("Payment Entry", payment_entry_id)
    except frappe.DoesNotExistError:
        return {"error": _("Payment Entry {0} not found.").format(payment_entry_id)}
    except Exception as e:
        return {"error": _("Error loading Payment Entry {0}: {1}").format(payment_entry_id, cstr(e))}

    # must be submitted
    if getattr(pe_doc, "docstatus", 0) != 1:
        return {"error": _("Payment Entry {0} is not submitted.").format(payment_entry_id)}

    # must be Receive type
    if (getattr(pe_doc, "payment_type", "") or "").lower() != "receive":
        return {"error": _("Payment Entry {0} is not of type 'Receive'.").format(payment_entry_id)}

    pe_amount = flt(getattr(pe_doc, "paid_amount", None)  or 0.0)

    # compute total already allocated in AR City Ledger Invoice Payment Entry,
    # excluding allocations that belong to the current ARCI (if provided)
    try:
        if current_arci:
            sql = """SELECT COALESCE(SUM(payment_amount), 0) 
                     FROM `tabAR City Ledger Invoice Payment Entry`
                     WHERE payment_entry_id=%s AND parent != %s"""
            total_allocated = flt(frappe.db.sql(sql, (payment_entry_id, current_arci))[0][0])
        else:
            sql = """SELECT COALESCE(SUM(payment_amount), 0) 
                     FROM `tabAR City Ledger Invoice Payment Entry`
                     WHERE payment_entry_id=%s"""
            total_allocated = flt(frappe.db.sql(sql, (payment_entry_id,))[0][0])
    except Exception as e:
        return {"error": _("Failed to compute allocated amount for Payment Entry {0}: {1}").format(payment_entry_id, cstr(e))}

    remaining = pe_amount - total_allocated
    if remaining < 0:
        remaining = 0.0

    return {
        "pe_amount": pe_amount,
        "total_allocated_excluding_current": total_allocated,
        "remaining": remaining
    }



@frappe.whitelist()
def remove_payment_entry_links(payment_entry_id):
    """
    Removes all rows in AR City Ledger Invoice that reference the given payment_entry_id,
    updates total_paid/outstanding and sets status from Paid->Unpaid if needed.
    Returns list of updated AR City Ledger Invoice names.
    """
    updated = []
    if not payment_entry_id:
        return updated

    # fetch all AR City Ledger Invoice parents that have such child rows
    rows = frappe.db.sql("""
        SELECT parent, name, payment_amount
        FROM `tabAR City Ledger Invoice Payment Entry`
        WHERE payment_entry_id = %s
    """, (payment_entry_id,), as_dict=True)

    parents = {}
    for r in rows:
        parent = r.parent
        parents.setdefault(parent, []).append(r)

    for parent_name, child_rows in parents.items():
        try:
            arci = frappe.get_doc("AR City Ledger Invoice", parent_name)
            total_removed = flt(sum([flt(r.payment_amount) for r in child_rows]))

            # remove rows referencing this payment_entry_id
            remaining_rows = [r for r in (arci.get("ar_city_ledger_invoice_payment_entry") or []) if r.payment_entry_id != payment_entry_id]
            arci.ar_city_ledger_invoice_payment_entry = remaining_rows

            # update totals
            arci.total_paid = flt(arci.total_paid) - total_removed
            if arci.total_paid < 0:
                arci.total_paid = 0.0

            arci.outstanding = flt(arci.outstanding) + total_removed

            # if it was Paid and now not fully paid, change to Unpaid
            if arci.status == "Paid":
                # recalc: if total_paid < total_amount => set Unpaid
                if flt(arci.total_paid) < flt(arci.total_amount):
                    arci.status = "Unpaid"

            arci.save(ignore_permissions=True)
            updated.append(parent_name)
        except Exception as e:
            frappe.log_error(f"Error while removing PE links from ARCI {parent_name} for PE {payment_entry_id}: {str(e)}", "ARCI_Remove_PE_Link_Error")

    return updated

@frappe.whitelist()
def make_journal_entry__discount(arci_name):
    """
    Create Journal Entry for discounts in AR City Ledger Invoice.
    - Sum all discount rows in AR City Ledger Invoice Discounts that are not yet linked to JE.
    - Ensure total_discount <= outstanding (do not allow negative outstanding).
    - Create and submit a Journal Entry:
        Debit: Discount Account (from Inn Hotels Setting)
        Credit: Customer Party Account (from Customer -> Party Account child table for company)
    - Link journal_entry_id to each discount row used.
    - Update total_discount, total_paid, outstanding on AR City Ledger Invoice.
    Returns: {"journal_entry": je.name, "total_discount": total_discount}
    """
    if not arci_name:
        frappe.throw(_("AR City Ledger Invoice id is required."))

    arci = frappe.get_doc("AR City Ledger Invoice", arci_name)

    if not arci.name:
        frappe.throw(_("Please save AR City Ledger Invoice before creating discount Journal Entry."))

    child_fieldname = "ar_city_ledger_invoice_discounts"
    discounts = arci.get(child_fieldname) or []

    # only rows not yet linked
    discount_rows_to_use = [r for r in discounts if not r.get("journal_entry_id") and flt(r.get("payment_amount")) > 0]

    if not discount_rows_to_use:
        frappe.throw(_("No discount rows available to create Journal Entry."))

    total_discount = flt(sum(flt(r.payment_amount) for r in discount_rows_to_use))

    outstanding = flt(arci.outstanding)
    if total_discount <= 0:
        frappe.throw(_("Total discount must be greater than zero."))
    if total_discount > outstanding:
        frappe.throw(_("Total discount ({0}) exceeds the invoice outstanding ({1}).").format(total_discount, outstanding))

    # get discount account
    hotel_settings = frappe.get_single("Inn Hotels Setting")
    discount_account = hotel_settings.get("discount_account")
    if not discount_account:
        frappe.throw(_("Please configure Discount Account in Inn Hotels Setting."))

    company = frappe.get_doc("Global Defaults").default_company
    customer = arci.customer_id
    if not customer:
        frappe.throw(_("AR City Ledger Invoice has no Contact Person (Customer)."))

    # find Party Account row for this company
    party_account = frappe.db.get_value("Party Account", {"parent": customer, "company": company}, "account")
    if not party_account:
        party_account = frappe.db.get_value("Party Account", {"parent": customer}, "account")
    if not party_account:
        frappe.throw(_("No Party Account found for Customer {0}. Please set Party Account under the Customer.").format(customer))

    # create JE
    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Journal Entry"
    je.posting_date = arci.issued_date or frappe.utils.nowdate()
    je.company = company
    je.title = _("Discount for {0}").format(arci.name)
    je.remark = _("Discount applied from AR City Ledger Invoice {0}").format(arci.name)

    je.append("accounts", {
        "account": discount_account,
        "debit": total_discount,
        "credit": 0.0,
        "debit_in_account_currency": total_discount,
        "credit_in_account_currency": 0.0,
        "user_remark": _("Discount for {0}").format(arci.name),
    })

    je.append("accounts", {
        "account": party_account,
        "credit": total_discount,
        "debit": 0.0,
        "credit_in_account_currency": total_discount,
        "debit_in_account_currency": 0.0,
        "party_type": "Customer",
        "party": customer,
        "user_remark": _("Discount applied to {0}").format(arci.name),
    })

    try:
        je.insert(ignore_permissions=True)
        je.submit()
    except Exception as e:
        frappe.log_error(message=cstr(e), title="Discount Journal Entry Creation Failed")
        frappe.throw(_("Failed to create/submit Journal Entry for discount: {0}").format(cstr(e)))

    # link rows in DB (single pass)
    for r in discount_rows_to_use:
        if r.get("name"):
            frappe.db.set_value("AR City Ledger Invoice Discounts", r.name, "journal_entry_id", je.name, update_modified=False)

    # Re-fetch parent and recompute totals deterministically from DB child tables
    arci = frappe.get_doc("AR City Ledger Invoice", arci_name)

    # compute total_paid from payments + payment_entry + applied discounts
    total_paid = 0.0
    for p in (arci.get("payments") or []):
        total_paid += flt(p.get("payment_amount", 0))
    for pe in (arci.get("ar_city_ledger_invoice_payment_entry") or []):
        total_paid += flt(pe.get("payment_amount", 0))
    # applied discounts = only rows with journal_entry_id
    applied_discount_total = 0.0
    for d in (arci.get("ar_city_ledger_invoice_discounts") or []):
        if d.get("journal_entry_id"):
            applied_discount_total += flt(d.get("payment_amount", 0))

    total_paid = flt(total_paid) + flt(applied_discount_total)

    # set fields on arci
    arci.total_discount = flt(applied_discount_total)
    arci.total_paid = flt(total_paid)
    arci.outstanding = flt(arci.total_amount or 0.0) - flt(arci.total_paid)
    if arci.outstanding < 0:
        arci.outstanding = 0.0
    if flt(arci.outstanding) == 0:
        arci.status = "Paid"

    arci.save(ignore_permissions=True)

    return {"journal_entry": je.name, "total_discount": applied_discount_total}

def on_journal_entry_cancel_discount(doc, method):
    """
    Hook to run when a Journal Entry is cancelled.
    - Finds discount child rows linked to this Journal Entry
    - Removes those child rows from their AR City Ledger Invoice
    - Reverts total_paid / outstanding and status on the parent AR City Ledger Invoice
    """
    je_name = doc.name

    # find all discount child rows referencing this JE
    linked_rows = frappe.get_all(
        "AR City Ledger Invoice Discounts",
        filters={"journal_entry_id": je_name},
        fields=["name", "parent", "payment_amount"]
    )

    if not linked_rows:
        return

    # group by parent invoice
    parents = {}
    for row in linked_rows:
        parent = row.parent
        parents.setdefault(parent, []).append(row)

    for parent_name, rows in parents.items():
        try:
            arci = frappe.get_doc("AR City Ledger Invoice", parent_name)
        except frappe.DoesNotExistError:
            frappe.log_error(_("AR City Ledger Invoice {0} not found while cancelling JE {1}").format(parent_name, je_name))
            continue

        total_removed = 0.0
        # remove rows from arci child table
        # best to reload latest child rows and remove those with matching journal_entry_id
        existing = arci.get("ar_city_ledger_invoice_discounts") or []
        remaining = []
        for r in existing:
            if r.get("journal_entry_id") == je_name:
                total_removed += flt(r.get("payment_amount") or 0.0)
            else:
                remaining.append(r)

        # set remaining as new child list
        arci.set("ar_city_ledger_invoice_discounts", remaining)

        # revert totals
        arci.total_paid = flt(arci.get("total_paid") or 0.0) - total_removed
        if arci.total_paid < 0:
            arci.total_paid = 0.0

        arci.outstanding = flt(arci.get("total_amount") or 0.0) - flt(arci.total_paid)
        if arci.outstanding < 0:
            arci.outstanding = 0.0

        # if invoice was Paid and now outstanding > 0, revert status
        if arci.status == "Paid" and flt(arci.outstanding) > 0:
            arci.status = "Unpaid"

        # also reduce total_discount if present
        if hasattr(arci, "total_discount"):
            arci.total_discount = flt(arci.get("total_discount") or 0.0) - total_removed
            if arci.total_discount < 0:
                arci.total_discount = 0.0

        arci.save(ignore_permissions=True)

    # After successful removal, nothing else needed.
