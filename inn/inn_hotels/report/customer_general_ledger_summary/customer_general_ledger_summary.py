# Copyright (c) 2025, Core Initiative and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from frappe import _

def execute(filters=None):
    """
    Main entry point for the Customer General Ledger Summary report.
    This function orchestrates the data retrieval, aggregation, and prepares
    the final report structure including columns, data rows, and a summary.

    Args:
        filters (dict): A dictionary of filter values applied by the user in the report interface.

    Returns:
        tuple: A tuple containing (columns, data, charts, report_summary),
               where charts are None as we don't have charts in this report.
    """
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)
    report_summary = get_report_summary(data)

    return columns, data, None, None, report_summary


def get_columns():
    """
    Defines the column structure for the Customer General Ledger Summary report.
    Each column includes a label (translatable), fieldname, fieldtype, and width.

    Returns:
        list: A list of dictionaries, each representing a column in the report.
    """
    return [
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 300,"bold": 1},
        {"label": _("Total Debit"), "fieldname": "total_debit", "fieldtype": "Currency", "width": 290, "bold": 1},
        {"label": _("Total Credit"), "fieldname": "total_credit", "fieldtype": "Currency", "width": 290, "bold": 1},
        {"label": _("Balance"), "fieldname": "balance", "fieldtype": "Currency", "width": 290, "bold": 1},
    ]


def get_data(filters):
    """
    Fetches General Ledger (GL) entries, applies special business rules,
    calculates opening balances per customer, and then aggregates total
    debit, credit, and balance for each customer within the reporting period.
    Finally, it adds an overall totals row.

    Args:
        filters (dict): Filter values from the report interface.

    Returns:
        list: A list of dictionaries, where each dictionary represents a row
              in the report (one row per customer, plus a total row).
    """
    final_report_data = []

    # 1. Calculate opening balances for each customer prior to the report's `from_date`.
    #    This ensures that the aggregated totals correctly reflect the balance carried forward.
    opening_balances_per_customer = calculate_opening_balances_per_customer(filters)

    # 2. Fetch GL entries that fall within the main reporting period (`from_date` to `to_date`).
    report_period_gl_entries = get_gl_entries(filters)
    
    # 3. Apply custom business rules (e.g., filtering entries based on remarks or account types)
    #    to the GL entries within the report period.
    report_period_gl_entries = apply_special_rules(report_period_gl_entries)

    # Dictionary to aggregate debit/credit totals for each customer.
    # It starts with opening balances and then adds transactions from the report period.
    customer_aggregated_totals = {} # Format: {customer_id: {'total_debit': X, 'total_credit': Y}}

    # Initialize customer_aggregated_totals with opening balances.
    # This correctly sets the starting point for each customer's totals.
    for customer_id, balance_data in opening_balances_per_customer.items():
        customer_aggregated_totals[customer_id] = {
            'total_debit': flt(balance_data['debit']),
            'total_credit': flt(balance_data['credit'])
        }

    # Aggregate debit/credit for GL entries occurring within the report period.
    for entry in report_period_gl_entries:
        customer_id = entry.party # 'party' field in GL Entry stores the Customer ID for customer-related entries.

        # Ensure the customer is in the aggregation dictionary. Initialize with 0 if not present
        # (e.g., customer has no opening balance but transactions in report period).
        customer_aggregated_totals.setdefault(customer_id, {'total_debit': 0.0, 'total_credit': 0.0})

        customer_aggregated_totals[customer_id]['total_debit'] += flt(entry.debit)
        customer_aggregated_totals[customer_id]['total_credit'] += flt(entry.credit)

    # Prepare the final data structure for the report by iterating through aggregated totals.
    for customer_id, totals in customer_aggregated_totals.items():
        # Calculate the final balance for each customer.
        customer_balance = totals['total_debit'] - totals['total_credit']
        final_report_data.append({
            'customer': customer_id,
            'total_debit': totals['total_debit'],
            'total_credit': totals['total_credit'],
            'balance': customer_balance
        })

    # Sort the customer data alphabetically by customer name for consistent report display.
    final_report_data = sorted(final_report_data, key=lambda x: x['customer'])

    # Add an overall totals row at the very bottom of the report table.
    # This row summarizes all customers' aggregated debit, credit, and final balance.
    overall_total_debit_sum = sum(row.get('total_debit', 0) for row in final_report_data)
    overall_total_credit_sum = sum(row.get('total_credit', 0) for row in final_report_data)
    overall_final_balance = overall_total_debit_sum - overall_total_credit_sum

    final_report_data.append({
        'customer': _("Overall Totals"), # Label for the totals row, translatable.
        'total_debit': overall_total_debit_sum,
        'total_credit': overall_total_credit_sum,
        'balance': overall_final_balance,
        'is_total': True # Custom flag used by JavaScript to apply special styling to this row.
    })

    return final_report_data


def get_gl_entries(filters):
    """
    Fetches General Ledger (GL) entries from the database based on provided filters.
    It specifically targets entries where party_type is 'Customer' and excludes cancelled entries.

    Args:
        filters (dict): A dictionary of filter criteria for the GL entries.

    Returns:
        list: A list of dictionaries, where each dictionary represents a GL entry.
    """
    conditions = ["party_type = 'Customer'", "is_cancelled = 0"]

    if filters.get("from_date"):
        conditions.append(f"posting_date >= '{filters['from_date']}'")
    if filters.get("to_date"):
        conditions.append(f"posting_date <= '{filters['to_date']}'")
    if filters.get("account"):
        conditions.append(f"account = '{filters['account']}'")
    if filters.get("customer"):
        conditions.append(f"party = '{filters['customer']}'")
    if filters.get("company"):
        conditions.append(f"company = '{filters['company']}'")

    final_conditions_str = " AND ".join(conditions)

    return frappe.db.sql(f"""
        SELECT posting_date, account, debit, credit, voucher_type, voucher_no, remarks, against, party
        FROM `tabGL Entry`
        WHERE {final_conditions_str}
        ORDER BY posting_date ASC
    """, as_dict=True)


def calculate_opening_balances_per_customer(filters):
    """
    Calculates the aggregate debit and credit for each relevant customer
    for all GL entries that occur *before* the `from_date` specified in the filters.
    Applies the same GL entry filtering and special business rules as the main report.

    Args:
        filters (dict): Filter criteria for the report.

    Returns:
        dict: A dictionary where keys are customer IDs and values are dictionaries
              containing 'debit', 'credit', and 'balance' for entries prior to `from_date`.
    """
    opening_balances_aggregated = {} # {customer_id: {'debit': X, 'credit': Y, 'balance': Z}}

    # If 'from_date' is not specified, there are no prior entries, so opening balance is zero.
    if not filters.get("from_date"):
        return opening_balances_aggregated 

    # Build conditions for GL entries occurring strictly PRIOR to the `from_date`.
    conditions = ["party_type = 'Customer'", f"posting_date < '{filters['from_date']}'", "is_cancelled = 0"]

    if filters.get("account"):
        conditions.append(f"account = '{filters['account']}'")
    if filters.get("customer"):
        conditions.append(f"party = '{filters['customer']}'")
    if filters.get("company"):
        conditions.append(f"company = '{filters['company']}'")

    final_conditions_str = " AND ".join(conditions)

    # Fetch these prior entries.
    prior_period_gl_entries = frappe.db.sql(f"""
        SELECT debit, credit, remarks, account, voucher_type, voucher_no, party
        FROM `tabGL Entry`
        WHERE {final_conditions_str}
    """, as_dict=True)

    # Apply the special business rules to these prior entries.
    prior_period_gl_entries = apply_special_rules(prior_period_gl_entries)
    
    # Aggregate debit and credit for each customer from these prior entries.
    for entry in prior_period_gl_entries:
        customer_id = entry.party
        opening_balances_aggregated.setdefault(customer_id, {'debit': 0.0, 'credit': 0.0})
        opening_balances_aggregated[customer_id]['debit'] += flt(entry.debit)
        opening_balances_aggregated[customer_id]['credit'] += flt(entry.credit)
    
    # Calculate the opening balance for each customer.
    for customer_id, totals in opening_balances_aggregated.items():
        totals['balance'] = totals['debit'] - totals['credit']

    return opening_balances_aggregated


def apply_special_rules(entries):
    """
    Applies business-specific logic to a list of GL entries.
    -   Removes entries where remarks contain 'close' (case-insensitive).
    -   For vouchers containing both '1310' and '1311' accounts, only debit entries are included.

    Args:
        entries (list): A list of dictionaries, each representing a GL entry.

    Returns:
        list: A filtered list of GL entries after applying the rules.
    """
    filtered_entries_after_rules = []
    
    # Group entries by voucher to apply rules at a voucher level.
    grouped_by_voucher = {}
    for entry in entries:
        key = (entry.voucher_type, entry.voucher_no) # Use voucher type and number as a unique key for grouping.
        grouped_by_voucher.setdefault(key, []).append(entry)

    for key_tuple, entry_list_for_voucher in grouped_by_voucher.items():
        # Rule 1: Skip vouchers that contain 'close' in remarks.
        if any("close" in (entry.remarks or "").lower() for entry in entry_list_for_voucher):
            continue

        accounts_in_voucher = [entry.account for entry in entry_list_for_voucher]

        # Rule 2: If both accounts containing '1310' and '1311' exist in a voucher,
        #         only include debit entries from that voucher.
        has_1310_account = any("1310" in account for account in accounts_in_voucher)
        has_1311_account = any("1311" in account for account in accounts_in_voucher)

        if has_1310_account and has_1311_account:
            # Add only debit entries from this voucher.
            filtered_entries_after_rules += [entry for entry in entry_list_for_voucher if entry.debit > 0]
        else:
            # Otherwise, include all entries from this voucher.
            filtered_entries_after_rules += entry_list_for_voucher

    return filtered_entries_after_rules


def get_report_summary(data):
    """
    Calculates overall summary totals (Total Debit, Total Credit, Overall Balance)
    for the entire report, excluding the 'Overall Totals' row itself if it's part of `data`.

    Args:
        data (list): The list of data rows generated for the report (including the totals row).

    Returns:
        list: A list of dictionaries, each representing a summary item for the report header.
    """
    # Sum only actual customer rows, exclude the 'Overall Totals' row from this calculation.
    # The 'is_total' flag is used to identify the totals row.
    total_debit_sum = sum(flt(row.get("total_debit", 0)) for row in data if not row.get('is_total'))
    total_credit_sum = sum(flt(row.get("total_credit", 0)) for row in data if not row.get('is_total'))
    overall_balance = total_debit_sum - total_credit_sum

    return [
        {
            "value": total_debit_sum,
            "label": _("Overall Total Debit"),
            "datatype": "Currency",
            "indicator": "blue"
        },
        {
            "value": total_credit_sum,
            "label": _("Overall Total Credit"),
            "datatype": "Currency",
            "indicator": "red"
        },
        {
            "value": overall_balance,
            "label": _("Overall Balance"),
            "datatype": "Currency",
            "indicator": "green" if overall_balance >= 0 else "orange" # Green for positive/zero balance, orange for negative.
        }
    ]
