# -*- coding: utf-8 -*-
# Copyright (c) 2020, Core Initiative and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import math
import json
import datetime
from frappe.utils import flt
from frappe.model.document import Document


class InnFolio(Document):
    pass

    # def validate(self):

    #     settings = frappe.get_single("Inn Hotels Setting")
    #     for trx in self.folio_transaction:
    #         if (
    #             trx.is_void == 0
    #             and trx.amount <= 0
    #             and not settings.allow_negative_transaction_value
    #         ):

    #             frappe.throw("Amount must be greater than 0 for non-void transaction.")


@frappe.whitelist()
def create_folio(reservation_id):
    if not frappe.db.exists("Inn Folio", {"reservation_id": reservation_id}):
        reservation = frappe.get_doc("Inn Reservation", reservation_id)

        doc = frappe.new_doc("Inn Folio")
        doc.type = "Guest"
        doc.reservation_id = reservation_id
        doc.customer_id = reservation.customer_id
        doc.open = reservation.expected_arrival
        doc.close = reservation.expected_departure
        doc.insert()


def update_close_by_reservation(reservation_id):
    folio_list = frappe.get_all("Inn Folio", filters={"reservation_id": reservation_id})
    reservation = frappe.get_doc("Inn Reservation", reservation_id)
    # Update except status finish, because when Checking Out, Close is handled by close_folio function
    if reservation.status != "Finish":
        for item in folio_list:
            doc_folio = frappe.get_doc("Inn Folio", item.name)
            doc_folio.close = reservation.departure.strftime("%Y-%m-%d")
            doc_folio.save()


@frappe.whitelist()
def get_reservation_id(folio_id):
    doc = frappe.get_doc("Inn Folio", folio_id)
    return doc.reservation_id


@frappe.whitelist()
def update_balance(folio_id):
    doc = frappe.get_doc("Inn Folio", folio_id)
    if doc.status=="Closed":
        return doc.total_debit, doc.total_credit,doc.balance #if status=closed return
    trx_list = doc.get("folio_transaction")
    total_debit = 0.0
    total_credit = 0.0
    for trx in trx_list:
        if trx.flag == "Debit" and trx.is_void == 0:
            total_debit += float(trx.amount)
        elif trx.flag == "Credit" and trx.is_void == 0:
            total_credit += float(trx.amount)
    balance = total_credit - math.ceil(total_debit)
    excess_amount=balance if balance>0 else 0  #adding the result

    if balance != doc.balance or flt(excess_amount) != flt(doc.excess_amount) :
        frappe.db.set_value(
            "Inn Folio", doc.name, "total_debit", math.ceil(total_debit)
        )
        frappe.db.set_value("Inn Folio", doc.name, "total_credit", total_credit)
        frappe.db.set_value("Inn Folio", doc.name, "balance", int(balance))
        frappe.db.set_value("Inn Folio",doc.name,"excess_amount",excess_amount) #set new value of excess

    return total_debit, total_credit, balance


@frappe.whitelist()
def need_to_update_balance(folio_id):
    doc = frappe.get_doc("Inn Folio", folio_id)
    trx_list = doc.get("folio_transaction")

    total_debit = 0.0
    total_credit = 0.0
    for trx in trx_list:
        if trx.flag == "Debit" and trx.is_void == 0:
            total_debit += float(trx.amount)
        elif trx.flag == "Credit" and trx.is_void == 0:
            total_credit += float(trx.amount)
    balance = total_credit - total_debit
   
    if balance != doc.balance or flt(max(balance,0))!=flt(doc.excess_amount):#check if excess need to change 
        return 1
    else:
        return 0


@frappe.whitelist()
def get_balance(folio_id):
    update_balance(folio_id)
    return frappe.db.get_value("Inn Folio", folio_id, ["balance"])


@frappe.whitelist()
def get_balance_by_reservation(reservation_id):
    folio = frappe.get_doc("Inn Folio", {"reservation_id": reservation_id})
    balance = get_balance(folio.name)
    return balance


@frappe.whitelist()
def transfer_to_another_folio(trx_list, old_parent, new_parent):
    exist_error = 0
    list_json = json.loads(trx_list)
    for trx in list_json:
        trx_doc = frappe.get_doc("Inn Folio Transaction", trx)
        if trx_doc.parent == old_parent:
            trx_doc.parent = new_parent
            trx_doc.remark = (
                "Transferred from " + old_parent + " to Folio " + new_parent
            )
            trx_doc.save()
        else:
            exist_error = 1

    return exist_error


def is_using_city_ledger(folio_id):
    is_using = False
    doc = frappe.get_doc("Inn Folio", folio_id)
    trx_list = doc.get("folio_transaction")
    hotel_settings = frappe.get_doc("Inn Hotels Setting")

    for trx in trx_list:
        if (
            trx.is_void == 0
            and trx.flag == "Credit"
            and trx.mode_of_payment == hotel_settings.city_ledger_mode_of_payment
        ):
            is_using = True
    return is_using

@frappe.whitelist()
def credit_excess_to_customer(folio_id):#limit dublicate of sending
    from erpnext.accounts.party import get_party_account
    from inn.inn_hotels.doctype.inn_audit_log.inn_audit_log import get_last_audit_date
    values = frappe.db.get_value(
        "Inn Folio", folio_id,
        ["excess_amount", "excess_credited", "customer_id"],
        as_dict=True,
    )
    excess_amount = flt(values.excess_amount)
    sending=excess_amount-flt(values.excess_credited)
    if sending<=0:
        return
  
    mode_of_payment = "Cash"
    company = frappe.get_doc("Global Defaults").default_company
    paid_to = frappe.db.get_value(
        "Mode of Payment Account",
        {"parent": mode_of_payment, "company": company},
        "default_account",
    )
    new_payment = frappe.new_doc("Payment Entry")
    new_payment.payment_type = "Receive"
    new_payment.posting_date = get_last_audit_date()
    new_payment.mode_of_payment = mode_of_payment
    new_payment.party_type = "Customer"
    new_payment.party = values.customer_id
    new_payment.company = company
    new_payment.paid_from = get_party_account("Customer", values.customer_id, company)
    new_payment.paid_to = paid_to
    new_payment.paid_amount = sending
    new_payment.received_amount = sending
    new_payment.insert()
    new_payment.submit()
    frappe.db.set_value("Inn Folio", folio_id, "excess_credited", excess_amount)


@frappe.whitelist()
def close_folio(folio_id):
    hotel_settings = frappe.get_doc("Inn Hotels Setting")

    list = check_void_request(folio_id)
    if len(list) == 0:
        update_balance(folio_id)
        balance = frappe.db.get_value("Inn Folio", folio_id, "balance")
        if balance < 0:
            return "Balance is negative. There are still transactions needed to be resolved."
        credit_excess_to_customer(folio_id)
        folio = frappe.get_doc("Inn Folio", folio_id)
        folio.balance=0 #remaining differnce to zero
        folio.status = "Closed"
        folio.close = datetime.date.today()
        folio.save()

        # Create AR City Ledger if There are payment using City Ledger as mode_of_payment
        if is_using_city_ledger(folio_id):
            total_amount = 0.0
            trx_list = frappe.get_all(
                "Inn Folio Transaction",
                filters={
                    "parent": folio_id,
                    "is_void": 0,
                    "flag": "Credit",
                    "mode_of_payment": hotel_settings.city_ledger_mode_of_payment,
                },
                fields=["amount"],
            )
            for trx in trx_list:
                total_amount += trx.amount

            ar_city_ledger = frappe.new_doc("AR City Ledger")
            ar_city_ledger.naming_series = "AR-CL-.YYYY.-"
            ar_city_ledger.is_paid = 0
            ar_city_ledger.customer_id = folio.customer_id
            if folio.type == "Guest":
                ar_city_ledger.inn_channel_id = frappe.db.get_value(
                    "Inn Reservation", folio.reservation_id, "channel"
                )
            else:
                ar_city_ledger.inn_group_id = folio.group_id
            ar_city_ledger.total_amount = total_amount
            ar_city_ledger.folio_id = folio_id
            ar_city_ledger.folio_type = folio.type
            ar_city_ledger.folio_status = folio.status
            ar_city_ledger.folio_open = folio.open
            ar_city_ledger.folio_close = folio.close
            ar_city_ledger.insert()

        return frappe.db.get_value("Inn Folio", folio_id, "status")
    else:
        return (
            "There are void transaction request that still not responded. "
            "Please consult the supervisor to resolve this before closing Folio."
            + "<br /> Transaction need to be resolved: <br />"
            + list
        )


@frappe.whitelist()
def check_void_request(folio_id):
    need_resolve = []
    folio = frappe.get_doc("Inn Folio", folio_id)
    trx_list = folio.get("folio_transaction")
    for item in trx_list:
        if item.is_void == 0 and item.void_id is not None:
            if (
                frappe.db.get_value(
                    "Inn Void Folio Transaction", {"name": item.void_id}, "status"
                )
                == "Requested"
            ):
                need_resolve.append(item.name)
    return need_resolve
