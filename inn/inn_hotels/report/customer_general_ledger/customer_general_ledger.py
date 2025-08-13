# Copyright (c) 2025, Core Initiative and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from frappe import _

def execute(filters=None):
    """
    Main entry point for the report. Applies filters, fetches GL entries,
    applies special business rules, calculates balances, and returns
    columns and structured data.
    """
    if not filters:
        filters = {}

    columns = get_columns()
    data = []

    # Fetch GL Entries with filters (excluding cancelled ones)
    gl_entries = get_gl_entries(filters)

    # Apply custom business rules
    filtered_entries = apply_special_rules(gl_entries)

    # Sort entries by posting date
    filtered_entries = sorted(filtered_entries, key=lambda x: x.posting_date)

    # Calculate opening balance before from_date
    total_debit, total_credit, opening_balance = calculate_opening_balance(filtered_entries, filters)
    running_balance = opening_balance
    
    # Initialize closing totals
    closing_debit = 0.0
    closing_credit = 0.0

    # Add opening balance row
    data.append({
        "posting_date": "",
        "account": "",
        "debit": total_debit,
        "credit": total_credit,
        "balance": opening_balance,
        "voucher_type": "Opening",
        "voucher_no": "",
        "against_account": ""
    })

    # Process each GL entry and update running balance
    for entry in filtered_entries:
        running_balance += flt(entry.debit) - flt(entry.credit)
        closing_debit += flt(entry.debit) + total_debit
        closing_credit += flt(entry.credit) + total_credit
        data.append({
            "posting_date": entry.posting_date,
            "account": entry.account,
            "debit": entry.debit,
            "credit": entry.credit,
            "balance": running_balance,
            "voucher_type": entry.voucher_type,
            "voucher_no": entry.voucher_no,
            "against_account": entry.against
        })

    # Add closing balance row
    data.append({
        "posting_date": "",
        "account": "Total",
        "debit": closing_debit,
        "credit": closing_credit,
        "balance": running_balance,
        "voucher_type": "Closing",
        "voucher_no": "",
        "against_account": ""
    })

    return columns, data


def get_columns():
    """
    Defines the column structure of the report.
    """
    return [
        {"label": '<i class="fa fa-calendar" style="color: #3F51B5;"></i> ' + _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
        {"label": '<i class="fa fa-barcode" style="color: #2196F3;"></i> '+ _("Account"), "fieldname": "account", "fieldtype": "Link", "options": "Account", "width": 250},
        {"label": '<i class="fa fa-arrow-down" style="color: #009688;"></i> ' + _("Debit"), "fieldname": "debit", "fieldtype": "Currency", "width": 120},
        {"label": '<i class="fa fa-arrow-up" style="color: #F44336;"></i> ' + _("Credit"), "fieldname": "credit", "fieldtype": "Currency", "width": 120},
        {"label": '<i class="fa fa-balance-scale" style="color: #9C27B0;"></i> ' + _("Balance"), "fieldname": "balance", "fieldtype": "Currency", "width": 130},
        {"label": '<i class="fa fa-file-invoice" style="color: #795548;"></i> ' + _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 120},
        {"label": '<i class="fa fa-tag" style="color: #4CAF50;"></i> ' + _("Voucher No"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 250},
        {"label": '<i class="fa fa-barcode" style="color: #2196F3;"></i> ' + _("Against Account"), "fieldname": "against_account", "fieldtype": "Data", "width": 250},
    ]


def get_gl_entries(filters):
    """
    Fetch GL entries for Customers only, with filters.
    Excludes cancelled entries (`is_cancelled = 0`).
    """
    conditions = "party_type = 'Customer'"  # Force only Customers

    if filters.get("from_date"):
        conditions += f" AND posting_date >= '{filters['from_date']}'"
    if filters.get("to_date"):
        conditions += f" AND posting_date <= '{filters['to_date']}'"
    if filters.get("account"):
        conditions += f" AND account = '{filters['account']}'"
    if filters.get("customer"):
        conditions += f" AND party = '{filters['customer']}'"
    if filters.get("company"):
        conditions += f" AND company = '{filters['company']}'"

    # Exclude cancelled documents
    conditions += " AND is_cancelled = 0"

    return frappe.db.sql(f"""
        SELECT posting_date, account, debit, credit, voucher_type, voucher_no, remarks, against
        FROM `tabGL Entry`
        WHERE {conditions}
        ORDER BY posting_date ASC
    """, as_dict=True)


def apply_special_rules(entries):
    """
    Applies business-specific logic:
    - Removes entries with 'close' in remarks.
    - If both accounts containing '1310' and '1311' exist in a voucher, only include debit entries.
    """
    result = []
    grouped_by_voucher = {}

    for entry in entries:
        key = (entry.voucher_type, entry.voucher_no)
        grouped_by_voucher.setdefault(key, []).append(entry)

    for key, entry_list in grouped_by_voucher.items():
        # Skip vouchers that contain 'close' in remarks
        if any("close" in (e.remarks or "").lower() for e in entry_list):
            continue

        accounts = [e.account for e in entry_list]

        # Check if any account contains '1310' or '1311'
        has_1310 = any("1310" in account for account in accounts)
        has_1311 = any("1311" in account for account in accounts)

        if has_1310 and has_1311:
            # Include only debit entries
            result += [e for e in entry_list if e.debit > 0]
        else:
            result += entry_list

    return result


def calculate_opening_balance(entries, filters):
    """
    Calculates the opening balance prior to the `from_date`.
    Applies the same filtering and special rules.
    """
    if not filters.get("from_date"):
        return 0.0

    conditions = f"posting_date < '{filters['from_date']}' AND party_type = 'Customer'"  # Force only Customers

    if filters.get("account"):
        conditions += f" AND account = '{filters['account']}'"
    if filters.get("customer"):
        conditions += f" AND party = '{filters['customer']}'"
    if filters.get("company"):
        conditions += f" AND company = '{filters['company']}'"

    # Exclude cancelled documents in opening balance
    conditions += " AND is_cancelled = 0"

    old_entries = frappe.db.sql(f"""
        SELECT debit, credit, remarks, account, voucher_type, voucher_no
        FROM `tabGL Entry`
        WHERE {conditions}
    """, as_dict=True)

    # Apply business rules to the old entries as well
    old_entries = apply_special_rules(old_entries)
    total_debit = sum(flt(e.debit) for e in old_entries)
    total_credit = sum(flt(e.credit) for e in old_entries)
    balance = total_debit - total_credit
    return total_debit,total_credit,balance