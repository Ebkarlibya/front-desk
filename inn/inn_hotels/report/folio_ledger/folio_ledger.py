from dataclasses import field
import frappe
from frappe.utils import flt
from frappe import _
from collections import Counter


def execute(filters=None):
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

    # if filters.get("group_by_folio"):

    return columns, group_by_folio(filtered_entries)

    # Calculate opening balance before from_date
    # opening_debit, opening_credit, opening_balance = calculate_opening_balance(
    #     filtered_entries, filters
    # )
    # running_balance = opening_balance

    # Add opening balance row
    # data.append(
    #     {
    #         "posting_date": "",
    #         "account": "Opening",
    #         "debit": opening_debit,
    #         "credit": opening_credit,
    #         "balance": opening_balance,
    #         "voucher_type": "",
    #         "voucher_no": "",
    #         "against_account": "",
    #         "remarks": "",
    #     }
    # )

    # Initialize totals for current period (excluding opening)
    # period_debit = 0.0
    # period_credit = 0.0

    # # Process GL entries & calculate running balance

    # for entry in filtered_entries:
    #     debit = flt(entry.debit)
    #     credit = flt(entry.credit)

    #     running_balance += debit - credit
    #     period_debit += debit
    #     period_credit += credit

    #     data.append(
    #         {
    #             "posting_date": entry.posting_date,
    #             "account": entry.account,
    #             "debit": debit,
    #             "credit": credit,
    #             "balance": running_balance,
    #             "voucher_type": entry.voucher_type,
    #             "voucher_no": entry.voucher_no,
    #             "against_account": entry.against,
    #             "remarks": entry.remarks or "",
    #         }
    #     )

    # # Add total row (current period only)
    # data.append(
    #     {
    #         "posting_date": "",
    #         "account": "Total",
    #         "debit": period_debit,
    #         "credit": period_credit,
    #         "balance": period_debit - period_credit,
    #         "voucher_type": "",
    #         "voucher_no": "",
    #         "against_account": "",
    #         "remarks": "",
    #     }
    # )

    # # Calculate closing balance = opening + period
    # closing_debit = opening_debit + period_debit
    # closing_credit = opening_credit + period_credit
    # closing_balance = closing_debit - closing_credit

    # # Add closing balance row
    # data.append(
    #     {
    #         "posting_date": "",
    #         "account": "Closing (Opening + Total)",
    #         "debit": closing_debit,
    #         "credit": closing_credit,
    #         "balance": closing_balance,
    #         "voucher_type": "",
    #         "voucher_no": "",
    #         "against_account": "",
    #         "remarks": "",
    #     }
    # )

    # return columns, data


def group_by_folio(filtered_entries):
    folios = {"ORPHAN": []}
    data = []
    for entry in filtered_entries:
        folio = frappe.db.get_value(
            "Inn Folio Transaction",
            filters={"journal_entry_id": entry["voucher_no"]},
            fieldname=["parent"],
        )
        if not folio:
            folios["ORPHAN"].append(entry)
            continue
        else:
            if not folios.get(folio):
                folios[folio] = []
            folios[folio].append(entry)
    # for key, values in folios.items():
    #     mock_entry = {
    #         "posting_date": "",
    #         "account": key,
    #         "debit": "",
    #         "credit": "",
    #         "voucher_type": "",
    #         "voucher_no": "",
    #         "remarks": "",
    #         "against": "",
    #         "party": "",
    #         "indent": 0,
    #     }
    #     data.append(mock_entry)
    #     for v in values:
    #         v["indent"] = 1
    #         data.append(v)

    balance = 0
    period_debit = 0
    period_credit = 0
    for key, values in folios.items():
        mock_entry = {
            "posting_date": "",
            "account": key,
            "debit": 0,
            "credit": 0,
            "balance": 0,
            "voucher_type": "",
            "voucher_no": "",
            "remarks": "",
            "against": "",
            "party": "",
            "indent": 0,
        }

        if key == "ORPHAN":
            data.append(mock_entry)
        for v in values:
            if key == "ORPHAN":
                v["indent"] = 1
                data.append(v)
            else:
                mock_entry["debit"] += v["debit"]
                mock_entry["credit"] += v["credit"]
                balance += v["debit"] - v["credit"]
                mock_entry["balance"] = balance
                period_debit += v["debit"]
                period_credit += v["credit"]
        if key != "ORPHAN":
            data.append(mock_entry)

    data.append(
        {
            "posting_date": "",
            "account": "Closing (Total)",
            "debit": period_debit,
            "credit": period_credit,
            "balance": balance,
            "voucher_type": "",
            "voucher_no": "",
            "against_account": "",
            "remarks": "",
        }
    )

    return data


def get_columns():
    """
    Defines the column structure of the report.
    """
    return [
        {
            "label": '<i class="fa fa-calendar" style="color: #3F51B5;"></i> '
            + _("Posting Date"),
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "label": '<i class="fa fa-barcode" style="color: #2196F3;"></i> '
            + _("Folio"),
            "fieldname": "account",
            "fieldtype": "Link",
            "options": "Inn Folio",
            "width": 250,
        },
        {
            "label": '<i class="fa fa-arrow-down" style="color: #009688;"></i> '
            + _("Debit"),
            "fieldname": "debit",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": '<i class="fa fa-arrow-up" style="color: #F44336;"></i> '
            + _("Credit"),
            "fieldname": "credit",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": '<i class="fa fa-balance-scale" style="color: #9C27B0;"></i> '
            + _("Balance"),
            "fieldname": "balance",
            "fieldtype": "Currency",
            "width": 130,
        },
        {
            "label": '<i class="fa fa-file-invoice" style="color: #795548;"></i> '
            + _("Voucher Type"),
            "fieldname": "voucher_type",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": '<i class="fa fa-tag" style="color: #4CAF50;"></i> '
            + _("Voucher No"),
            "fieldname": "voucher_no",
            "fieldtype": "Dynamic Link",
            "options": "voucher_type",
            "width": 250,
        },
        {
            "label": '<i class="fa fa-barcode" style="color: #2196F3;"></i> '
            + _("Against Account"),
            "fieldname": "against_account",
            "fieldtype": "Data",
            "width": 250,
        },
        {
            "label": '<i class="fa fa-comment" style="color: #607D8B;"></i> '
            + _("Remarks"),
            "fieldname": "remarks",
            "fieldtype": "Data",
            "width": 300,
        },
    ]


def get_gl_entries(filters):
    """
    Fetch GL entries for Customers only, with filters.
    Excludes cancelled entries (`is_cancelled = 0`).
    """
    conditions = "party_type = 'Customer'"

    if filters.get("from_date"):
        conditions += f" AND posting_date >= '{filters['from_date']}'"
    if filters.get("to_date"):
        conditions += f" AND posting_date <= '{filters['to_date']}'"
    # if filters.get("account"):
    #     conditions += f" AND account = '{filters['account']}'"
    if filters.get("customer"):
        conditions += f" AND party = '{filters['customer']}'"
    if filters.get("company"):
        conditions += f" AND company = '{filters['company']}'"

    conditions += " AND is_cancelled = 0"

    return frappe.db.sql(
        f"""
        SELECT posting_date, account, debit, credit, voucher_type, voucher_no, remarks, against, party
        FROM `tabGL Entry`
        WHERE {conditions}
        ORDER BY posting_date ASC
    """,
        as_dict=True,
    )


def apply_special_rules(entries):
    """
    Applies business-specific logic:
    - Removes entries with 'close' in remarks.
    - If both accounts containing '1310' and '1311' exist in a voucher, only include debit entries.
    """
    result = []
    grouped_by_voucher = {}
    customers = []
    journal_entry_ids = []

    for entry in entries:

        key = (entry.voucher_type, entry.voucher_no)
        grouped_by_voucher.setdefault(key, []).append(entry)
        if entry.party and entry.party not in customers:
            customers.append(entry.party)
    folios = []
    for customer in customers:
        mode_of_payment = frappe.get_single(
            "Inn Hotels Setting"
        ).city_ledger_mode_of_payment
        folio_sql = f"""
                SELECT inf.name AS folio, inf.journal_entry_id_closed AS journal_entry_id, 'Closed' AS entry_type
                FROM `tabInn Folio` inf
                WHERE inf.customer_id = {frappe.db.escape(customer)}
                AND inf.journal_entry_id_closed IS NOT NULL

                UNION ALL

                SELECT inf.name AS folio, inft.journal_entry_id, 'Transaction' AS entry_type
                FROM `tabInn Folio` inf
                INNER JOIN `tabInn Folio Transaction` inft ON inf.name = inft.parent
                WHERE inf.customer_id = {frappe.db.escape(customer)} AND inft.mode_of_payment = {frappe.db.escape(mode_of_payment)}

                UNION ALL

                SELECT inf.name AS folio, inft.journal_entry_id, 'Transaction' AS entry_type
                FROM `tabInn Folio` inf
                INNER JOIN `tabInn Folio Transaction` inft ON inf.name = inft.parent
                WHERE inf.customer_id = {frappe.db.escape(customer)} AND inft.is_void = 1
            """
        folio_jv = frappe.db.sql(folio_sql, as_dict=True, debug=True)
        journal_entry_ids = [
            row.journal_entry_id for row in folio_jv if row.journal_entry_id
        ]
        folios = [row.folio for row in folio_jv if row.folio]

    for key, entry_list in grouped_by_voucher.items():
        # Skip vouchers that contain 'close' in remarks
        # if any("close" in (e.remarks or "").lower() for e in entry_list):
        #     continue
        if key[1] in journal_entry_ids:
            continue

        accounts = [e.account for e in entry_list]

        parties = [e.party for e in entry_list]
        party_counts = Counter(parties)

        # True if any party appears more than once
        has_duplicate_party = any(count > 1 for count in party_counts.values())

        # Check if any account contains '1310' or '1311'
        has_1310 = any("1310" in account for account in accounts)
        has_1311 = any("1311" in account for account in accounts)
        count_1310 = sum("1310" in account for account in accounts)

        if count_1310 > 1 or has_duplicate_party:
            continue

        # if has_1310 and has_1311:
        #     # Include only debit entries
        #     result += [e for e in entry_list if e.debit > 0]
        # else:
        result += entry_list

    return result


def calculate_opening_balance(entries, filters):
    """
    Calculates the opening balance prior to the `from_date`.
    Applies the same filtering and special rules.
    """
    if not filters.get("from_date"):
        return 0.0, 0.0, 0.0

    conditions = f"posting_date < '{filters['from_date']}' AND party_type = 'Customer'"

    if filters.get("account"):
        conditions += f" AND account = '{filters['account']}'"
    if filters.get("customer"):
        conditions += f" AND party = '{filters['customer']}'"
    if filters.get("company"):
        conditions += f" AND company = '{filters['company']}'"

    conditions += " AND is_cancelled = 0"

    old_entries = frappe.db.sql(
        f"""
        SELECT debit, credit, remarks, account, voucher_type, voucher_no, party
        FROM `tabGL Entry`
        WHERE {conditions}
    """,
        as_dict=True,
    )

    # Apply business rules
    old_entries = apply_special_rules(old_entries)
    total_debit = sum(flt(e.debit) for e in old_entries)
    total_credit = sum(flt(e.credit) for e in old_entries)
    balance = total_debit - total_credit
    return total_debit, total_credit, balance
