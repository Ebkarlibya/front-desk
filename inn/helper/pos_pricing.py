import json
import frappe
from frappe.utils import flt, today

logger = frappe.logger("inn.pos_pricing")


def get_candidate_item_codes(item_code):
    """
    Returns candidate item codes for matching between POS items (e.g. '10037 (POS)')
    and inventory/base items (e.g. '10037') and vice versa.
    """
    if not item_code:
        return []

    candidates = [item_code]

    if " (POS)" in item_code:
        base = item_code.replace(" (POS)", "").strip()
        if base and base not in candidates:
            candidates.append(base)
    else:
        pos_variant = f"{item_code} (POS)"
        if pos_variant not in candidates:
            candidates.append(pos_variant)

    item_name = frappe.db.get_value("Item", item_code, "item_name")
    if item_name:
        same_name_items = frappe.db.get_all(
            "Item", filters={"item_name": item_name}, pluck="name"
        )
        for it in same_name_items:
            if it not in candidates:
                candidates.append(it)

    return candidates


def get_customer_or_profile_price_list(customer=None, pos_profile=None):
    """
    Returns customer default_price_list if configured.
    Otherwise falls back to POS Profile selling_price_list.
    """
    if customer:
        customer_price_list = frappe.db.get_value(
            "Customer", customer, "default_price_list"
        )
        if customer_price_list:
            logger.info(
                f"[POS Pricing] Customer '{customer}' has default_price_list: '{customer_price_list}'"
            )
            return customer_price_list

    if pos_profile:
        profile_price_list = frappe.db.get_value(
            "POS Profile", pos_profile, "selling_price_list"
        )
        if profile_price_list:
            logger.info(
                f"[POS Pricing] Customer '{customer}' has no default price list. "
                f"Falling back to POS Profile '{pos_profile}' selling_price_list: '{profile_price_list}'"
            )
            return profile_price_list

    fallback_pl = (
        frappe.db.get_single_value("Selling Settings", "selling_price_list")
        or "Standard Selling"
    )
    logger.info(
        f"[POS Pricing] Fallback to global selling_price_list: '{fallback_pl}'"
    )
    return fallback_pl


def get_folio_customer_price_list(folio_name, pos_profile=None):
    """
    Given an Inn Folio name, retrieves its customer_id and determines the correct price list.
    """
    if not folio_name:
        return {
            "customer": None,
            "price_list": get_customer_or_profile_price_list(pos_profile=pos_profile),
        }

    customer_id = frappe.db.get_value("Inn Folio", folio_name, "customer_id")
    price_list = get_customer_or_profile_price_list(
        customer=customer_id, pos_profile=pos_profile
    )
    logger.info(
        f"[POS Pricing] Folio '{folio_name}' -> Customer: '{customer_id}', Price List: '{price_list}'"
    )
    return {
        "customer": customer_id,
        "price_list": price_list,
    }


def get_item_price_rate(
    item_code,
    price_list,
    uom=None,
    transaction_date=None,
    fallback_price_list=None,
):
    """
    Fetches the selling rate for an item in a specific price list and UOM.
    Handles matching (POS) items with base items, and falls back to fallback_price_list
    if the item does not have a custom price entry in the primary price list.
    """
    if not item_code:
        return 0.0

    current_date = transaction_date or today()
    candidates = get_candidate_item_codes(item_code)

    def _query_price(pl):
        if not pl:
            return None
        ItemPrice = frappe.qb.DocType("Item Price")
        query = (
            frappe.qb.from_(ItemPrice)
            .select(ItemPrice.price_list_rate, ItemPrice.uom, ItemPrice.item_code)
            .where(ItemPrice.price_list == pl)
            .where(ItemPrice.item_code.isin(candidates))
            .where(ItemPrice.selling == 1)
            .where(
                (ItemPrice.valid_from <= current_date)
                | (ItemPrice.valid_from.isnull())
            )
            .where(
                (ItemPrice.valid_upto >= current_date)
                | (ItemPrice.valid_upto.isnull())
            )
            .orderby(ItemPrice.valid_from, order=frappe.qb.desc)
        )
        prices = query.run(as_dict=True)
        if not prices:
            return None

        if uom:
            for p in prices:
                if p.get("uom") == uom:
                    return flt(p.get("price_list_rate"))

        stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
        if stock_uom:
            for p in prices:
                if p.get("uom") == stock_uom:
                    return flt(p.get("price_list_rate"))

        return flt(prices[0].get("price_list_rate"))

    # 1. Check target price list
    rate = _query_price(price_list)
    if rate is not None:
        return rate

    # 2. Check fallback price list (e.g. POS Profile selling_price_list / Standard Selling)
    if fallback_price_list and fallback_price_list != price_list:
        rate = _query_price(fallback_price_list)
        if rate is not None:
            return rate

    # 3. Fallback to standard_rate on Item candidates
    for c in candidates:
        std_rate = frappe.db.get_value("Item", c, "standard_rate")
        if std_rate:
            return flt(std_rate)

    return 0.0


def recalculate_invoice_items_price(doc, target_price_list=None):
    """
    Recalculates rates for all items in a POS Invoice document using target_price_list
    with candidate item code matching and fallback to POS Profile price list.
    """
    if not target_price_list:
        target_price_list = get_customer_or_profile_price_list(
            customer=doc.get("customer"), pos_profile=doc.get("pos_profile")
        )

    if not target_price_list:
        return

    doc.selling_price_list = target_price_list
    posting_date = doc.get("posting_date") or today()
    fallback_pl = (
        frappe.db.get_value("POS Profile", doc.get("pos_profile"), "selling_price_list")
        if doc.get("pos_profile")
        else None
    )

    for item in doc.get("items", []):
        new_price = get_item_price_rate(
            item.get("item_code"),
            target_price_list,
            item.get("uom"),
            posting_date,
            fallback_price_list=fallback_pl,
        )
        if new_price:
            item.price_list_rate = new_price
            discount = flt(item.get("discount_percentage")) or 0.0
            item.rate = flt(new_price * (1.0 - discount / 100.0))
            item.amount = flt(item.rate * flt(item.get("qty", 1)))
            item.net_amount = item.amount

    if hasattr(doc, "calculate_taxes_and_totals"):
        doc.calculate_taxes_and_totals()

    logger.info(
        f"[POS Pricing] Recalculated items for invoice '{doc.get('name')}' using price list '{target_price_list}'"
    )


# ---------------------------------------------------------------------------
# Whitelisted API endpoints for POS frontend
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_resolved_price_list(customer=None, pos_profile=None):
    return get_customer_or_profile_price_list(
        customer=customer, pos_profile=pos_profile
    )


@frappe.whitelist()
def get_folio_pricing(folio_name, pos_profile=None):
    return get_folio_customer_price_list(
        folio_name=folio_name, pos_profile=pos_profile
    )


@frappe.whitelist()
def get_items(start, page_length, price_list, item_group, pos_profile, search_term=""):
    """
    Enhanced item fetcher for POS Extended that accurately populates price_list_rate
    by resolving candidate (POS) codes and falling back to pos_profile selling_price_list.
    """
    from erpnext.selling.page.point_of_sale.point_of_sale import (
        get_items as erpnext_get_items,
    )

    res = erpnext_get_items(
        start=start,
        page_length=page_length,
        price_list=price_list,
        item_group=item_group,
        pos_profile=pos_profile,
        search_term=search_term,
    )

    fallback_pl = (
        frappe.db.get_value("POS Profile", pos_profile, "selling_price_list")
        if pos_profile
        else None
    )
    items = res.get("items", []) if isinstance(res, dict) else res

    for it in items:
        rate = get_item_price_rate(
            it.get("item_code"),
            price_list=price_list,
            uom=it.get("uom") or it.get("stock_uom"),
            fallback_price_list=fallback_pl,
        )
        if rate:
            it["price_list_rate"] = rate

    return res


@frappe.whitelist()
def get_items_pricing_for_price_list(
    items, price_list, posting_date=None, pos_profile=None
):
    if isinstance(items, str):
        items = json.loads(items)

    fallback_pl = (
        frappe.db.get_value("POS Profile", pos_profile, "selling_price_list")
        if pos_profile
        else None
    )

    result = []
    for it in items:
        item_code = it.get("item_code")
        uom = it.get("uom")
        qty = flt(it.get("qty", 1))
        discount_percentage = flt(it.get("discount_percentage", 0))

        price_list_rate = get_item_price_rate(
            item_code,
            price_list,
            uom=uom,
            transaction_date=posting_date,
            fallback_price_list=fallback_pl,
        )
        rate = flt(price_list_rate * (1.0 - discount_percentage / 100.0))
        amount = flt(rate * qty)

        result.append(
            {
                "item_code": item_code,
                "uom": uom,
                "price_list_rate": price_list_rate,
                "rate": rate,
                "amount": amount,
                "net_amount": amount,
            }
        )

    return result
