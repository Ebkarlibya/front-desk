import frappe
from inn.helper.pos_pricing import (
    get_customer_or_profile_price_list,
    recalculate_invoice_items_price,
)


def validate(doc, method=None):
    target_price_list = get_customer_or_profile_price_list(
        customer=doc.customer, pos_profile=doc.pos_profile
    )
    if target_price_list and doc.selling_price_list != target_price_list:
        recalculate_invoice_items_price(doc, target_price_list)


def before_submit(doc, method=None):
    target_price_list = get_customer_or_profile_price_list(
        customer=doc.customer, pos_profile=doc.pos_profile
    )
    if target_price_list and doc.selling_price_list != target_price_list:
        recalculate_invoice_items_price(doc, target_price_list)

    doc.payments = [payment for payment in doc.payments if payment.amount != 0]
