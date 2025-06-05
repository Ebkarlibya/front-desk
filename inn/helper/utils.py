from erpnext import get_default_company
import frappe


def fetch_folio_accounts(trx):
    """Sets and returns debit/credit accounts for a folio transaction based on Mode of Payment and Transaction Type."""

    if trx.flag == "Debit":
        accounts = fetch_folio_debit_account(trx.transaction_type)
        # set_folio_debit_account(trx, accounts)

        return {
            "debit_account": accounts["credit"],
            "credit_account": accounts["debit"],
        }
    elif trx.flag == "Credit":

        default_company = get_default_company()

        # Get debit account from Mode of Payment Account
        debit_account = frappe.db.get_value(
            "Mode of Payment Account",
            {"parent": trx.mode_of_payment, "company": default_company},
            "default_account",
        )

        # Get credit account from Folio Transaction Type
        accounts = fetch_folio_debit_account(trx.transaction_type)
        credit_account = accounts["credit"]

        # set_folio_debit_account(trx, {"credit": credit_account, "debit": debit_account})
        # Update both accounts in one DB call
        return {
            "debit_account": debit_account,
            "credit_account": credit_account,
        }


def set_folio_debit_account(trx, accounts):
    """Sets debit and credit accounts in reverse order from the transaction type definition."""
    # accounts = fetch_folio_debit_account(trx.transaction_type)

    frappe.db.set_value(
        "Inn Folio Transaction",
        trx.name,
        {
            "debit_account": accounts["credit"],
            "credit_account": accounts["debit"],
        },
    )


def fetch_folio_debit_account(transaction_type):
    """Fetches debit and credit accounts from the Inn Folio Transaction Type."""
    accounts = frappe.db.get_value(
        "Inn Folio Transaction Type",
        {"name": transaction_type},
        ["debit_account", "credit_account"],
        as_dict=True,
    )
    return {"debit": accounts.debit_account, "credit": accounts.credit_account}


# def fetch_folio_credit_account(trx):
#     default_company = get_default_company()
#     debit_account = frappe.db.get_value(
#         "Mode of Payment Account",
#         {"parent": trx.mode_of_payment, "company": default_company},
#         "default_account",
#     )
#     credit_account = fetch_folio_debit_account(trx.transaction_type)["credit"]

#     frappe.db.set_value(
#         "Inn Folio Transaction",
#         trx.name,
#         "debit_account",
#         debit_account,
#     )
#     frappe.db.set_value(
#         "Inn Folio Transaction",
#         trx.name,
#         "credit_account",
#         credit_account,
#     )

#     return {
#         "debit_account": debit_account,
#         "credit_account": credit_account,
#     }


# def set_folio_debit_account(trx):

#     accounts = fetch_folio_debit_account(trx.transaction_type)

#     frappe.db.set_value(
#         "Inn Folio Transaction",
#         trx.name,
#         "debit_account",
#         accounts["credit_account"],
#     )
#     frappe.db.set_value(
#         "Inn Folio Transaction",
#         trx.name,
#         "credit_account",
#         accounts["debit_account"],
#     )


# def fetch_folio_debit_account(transaction_type):
#     accounts = frappe.db.get_value(
#         "Inn Folio Transaction Type",
#         {"parent": transaction_type},
#         ["debit_account", "credit_account"],
#         as_dict=True,
#     )
#     return {"credit": accounts.credit_account, "debit": accounts.debit_account}
