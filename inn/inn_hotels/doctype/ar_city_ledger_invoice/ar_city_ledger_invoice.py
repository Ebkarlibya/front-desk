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
