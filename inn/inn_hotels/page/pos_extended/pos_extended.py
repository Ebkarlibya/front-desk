import frappe
from inn.inn_hotels.doctype.inn_tax.inn_tax import calculate_inn_tax_and_charges
import json
from frappe import _
from frappe.utils import flt, get_datetime 

PRINT_STATUS_DRAFT = 0
PRINT_STATUS_CAPTAIN = 1
PRINT_STATUS_TABLE = 2
ORDER_FINISHED = 3

NEW_ORDER = 1


@frappe.whitelist()
def save_pos_usage(invoice_name, action, table=None):
    if action not in ["save_draft", "print_captain", "print_table", "save_submit"]:
        raise TypeError("argument error: action not found")

    new = False
    doc = ""
    if not frappe.db.exists({"doctype": "Inn POS Usage", "pos_invoice": invoice_name}):
        doc = frappe.new_doc("Inn POS Usage")

        if table != None and table != "":
            doc.table = table
            inn_table = frappe.get_doc("Inn Point Of Sale Table", table)
            inn_table.status = "Occupied"
            inn_table.save()

        doc.pos_invoice = invoice_name
        new = True

    else:
        doc = frappe.get_last_doc(
            "Inn POS Usage", filters={"pos_invoice": invoice_name}
        )
        # move table
        if doc.table != table:
            if doc.table != "" and doc.table is not None:
                doc_table = frappe.get_doc("Inn Point Of Sale Table", doc.table)
                doc_table.status = "Empty"
                doc_table.save()

            doc.table = table
            if table != None and table != "":
                doc_table = frappe.get_doc("Inn Point Of Sale Table", doc.table)
                doc_table.status = "Occupied"
                doc_table.save()

    # mainly change state except when flow repeated, will move tracked item to processed item and add new item to tracked item
    if (
        action in ["save_draft", "print_captain"]
        and doc.print_status == PRINT_STATUS_TABLE
        and not new
    ):
        # case if customer wants to add the order
        # then new item will be added to processed item
        # then new item will be empty to reset the tracked item
        items = doc.new_item
        doc.new_item = {}

        new_item = {x.item_name: x for x in items}
        tracked_item = {x.item_name: x for x in doc.processed_item}

        for i in new_item:
            if i in tracked_item:
                tracked_item[i].quantity += new_item[i].quantity
            else:
                tracked_item[i] = new_item[i]
                tracked_item[i].parentfield = "processed_item"

            tracked_item[i].save()

        doc.print_status = PRINT_STATUS_DRAFT
        doc.processed_item = {tracked_item[x] for x in tracked_item}

    if action == "save_draft" and doc.print_status == PRINT_STATUS_DRAFT:
        doc.print_status = PRINT_STATUS_DRAFT
    elif action == "print_captain" and doc.print_status == PRINT_STATUS_DRAFT:
        doc.print_status = PRINT_STATUS_CAPTAIN
    elif action == "print_table" and doc.print_status == PRINT_STATUS_CAPTAIN:
        doc.print_status = PRINT_STATUS_TABLE
    elif action == "save_submit":
        doc.print_status = ORDER_FINISHED

    else:
        raise frappe.DataError("print error: status not match")

    if action in ["save_draft", "print_captain"]:
        # add untracked child
        all_item = frappe.db.get_values(
            doctype="POS Invoice Item",
            filters={"parenttype": "POS Invoice", "parent": invoice_name},
            fieldname=["item_name", "qty"],
            as_dict=True,
        )

        if "tracked_item" not in locals():
            tracked_item = {x.item_name: x for x in doc.processed_item}

        new_item_name = {item.item_name: item for item in doc.new_item}
        doc.save()

        add_item = False
        for item in all_item:
            item_name = ""
            quantity = 0
            if item.item_name in tracked_item:
                diff = item.qty - tracked_item[item.item_name].quantity
                if diff > 0:
                    add_item = True
                    item_name = item.item_name
                    quantity = diff

            else:
                add_item = True
                item_name = item.item_name
                quantity = item.qty

            if add_item:
                if item_name in new_item_name:
                    new_item_name[item_name].quantity = quantity
                    new_item_name[item_name].save()

                else:
                    new_item = frappe.new_doc("Inn POS Usage Item")
                    new_item.item_name = item_name
                    new_item.quantity = quantity
                    new_item.parent = doc.name
                    new_item.parenttype = doc.doctype
                    new_item.parentfield = "new_item"
                    new_item.insert()
                add_item = False

    elif action in ["print_table", "save_submit"]:
        # no change. print table will use same data as print_captain
        doc.save()

    return {"message": "success"}


@frappe.whitelist()
def get_table_number(invoice_name):
    data = frappe.db.get_value(
        doctype="Inn POS Usage",
        filters={"pos_invoice": invoice_name},
        fieldname=["table", "transfer_to_folio"],
        as_dict=True,
    )
    if data:
        data["table_number"] = data["table"]
    return data

@frappe.whitelist()
def clean_table_number(invoice_name):
    table_name = frappe.get_last_doc(
        doctype="Inn POS Usage", filters={"pos_invoice": invoice_name}
    )
    table_name.print_status = ORDER_FINISHED
    table_name.save()

    if table_name.table is not None:
        doc_table = frappe.get_doc("Inn Point Of Sale Table", table_name.table)
        doc_table.status = "Empty"
        doc_table.save()
    return


@frappe.whitelist()
def transfer_to_folio(invoice_doc, folio_name):
    invoice_doc = json.loads(invoice_doc)
    if not frappe.db.exists(
        {"doctype": "Inn POS Usage", "pos_invoice": invoice_doc["name"]}
    ):
        raise ValueError(
            "save this transaction as draft first or print a captain order"
        )

    pos_usage = frappe.get_last_doc(
        "Inn POS Usage", filters={"pos_invoice": invoice_doc["name"]}
    )
    pos_usage.transfer_to_folio = folio_name
    pos_usage.save()

    # Fetch transaction types from Inn Hotels Setting
    hotel_settings = frappe.get_doc("Inn Hotels Setting")
    transaction_types = {
        "restaurant_food": hotel_settings.restaurant_food,
        "fbs_service_10": hotel_settings.fbs_service_10,
        "fbs_tax_11": hotel_settings.fbs_tax_11,
        "round_off": hotel_settings.round_off,
    }

    # Create Inn Folio Transaction Bundle
    ftb_doc = frappe.new_doc("Inn Folio Transaction Bundle")
    ftb_doc.transaction_type = "Restaurant Transfer Charges"
    ftb_doc.insert()

    idx = frappe.get_all(
        "Inn Folio Transaction",
        filters={
            "parent": folio_name,
            "parenttype": "Inn Folio",
            "parentfield": "folio_transaction",
        },
    )
    idx = len(idx)

    # Create folio transaction restaurant charge
    food_remark = (
        "Transfer Restaurant Food Charges from POS Order: " + invoice_doc["name"]
    )
    create_folio_trx(
        invoice_doc["name"],
        folio_name,
        invoice_doc["net_total"],
        transaction_types["restaurant_food"],
        ftb_doc,
        food_remark,
        idx,
    )
    idx = idx + 1

    # Create folio transaction restaurant tax and service
    guest_account_receivable = frappe.db.get_single_value(
        "Inn Hotels Setting", "guest_account_receiveable"
    )

    # Dynamic tax types and remarks
    tax_type = [transaction_types["fbs_service_10"], transaction_types["fbs_tax_11"]]
    remarks = [
        "Service of Transfer Restaurant Charges from POS Order: " + invoice_doc["name"],
        "Tax of Transfer Restaurant Charges from POS Order: " + invoice_doc["name"],
    ]

    if len(invoice_doc["taxes"]) == 1:
        # If the tax is only one, it's probably just a tax charge
        tax_type.pop(0)
        remarks.pop(0)

    for ii in range(len(invoice_doc["taxes"])):
        taxe = invoice_doc["taxes"][ii]
        create_folio_trx(
            invoice_doc["name"],
            folio_name,
            taxe["tax_amount_after_discount_amount"],
            tax_type[ii],
            ftb_doc,
            remarks[ii],
            idx,
            guest_account_receivable,
            taxe["account_head"],
        )
        idx = idx + 1

    if "rounding_adjustment" in invoice_doc and invoice_doc["rounding_adjustment"] != 0:
        roundoff_remark = (
            "Rounding off Amount of Transfer Restaurant Charges from Restaurant Order: "
            + invoice_doc["name"]
        )
        create_folio_trx(
            invoice_doc["name"],
            folio_name,
            invoice_doc["rounding_adjustment"],
            transaction_types["round_off"],
            ftb_doc,
            roundoff_remark,
            idx,
            guest_account_receivable,
        )

    ftb_doc.save()

    remove_pos_invoice_bill(invoice_doc["name"], folio_name)

@frappe.whitelist()
def get_past_order_list_with_table(search_term=None, status=None):
    company = frappe.defaults.get_user_default("company")

    conditions_list = ["`tabPOS Invoice`.company = %(company)s"]
    args = {"company": company}

    if status:
        conditions_list.append("`tabPOS Invoice`.status = %(status)s")
        args["status"] = status
    else:
         conditions_list.append("`tabPOS Invoice`.docstatus = 0")
    if search_term:
        search_pattern = "%" + search_term + "%"
        args["search_pattern"] = search_pattern
        search_conditions = [
            "`tabPOS Invoice`.customer LIKE %(search_pattern)s",
            "`tabPOS Invoice`.name LIKE %(search_pattern)s",
            """EXISTS (
                   SELECT 1
                   FROM `tabInn POS Usage` ipu_filter
                   WHERE ipu_filter.pos_invoice = `tabPOS Invoice`.name
                   AND ipu_filter.`table` LIKE %(search_pattern)s
               )"""
        ]
        conditions_list.append(f"({' OR '.join(search_conditions)})")

    conditions = "WHERE\n            " + "\n            AND ".join(conditions_list)

    query = f"""
        SELECT
            `tabPOS Invoice`.name,
            `tabPOS Invoice`.customer,
            `tabPOS Invoice`.grand_total,
            `tabPOS Invoice`.posting_date,
            `tabPOS Invoice`.posting_time,
            `tabPOS Invoice`.currency,
            `tabPOS Invoice`.status,
            -- `tabPOS Invoice`.docstatus, -- يمكنك إضافته إذا أردت رؤيته
            (SELECT ipu.`table`
             FROM `tabInn POS Usage` ipu
             WHERE ipu.pos_invoice = `tabPOS Invoice`.name
             ORDER BY ipu.modified DESC, ipu.creation DESC
             LIMIT 1) AS table_number
        FROM
            `tabPOS Invoice`
        {conditions}
        ORDER BY
            `tabPOS Invoice`.modified DESC
    """

    invoices = frappe.db.sql(query, args, as_dict=1)

    return invoices

def create_folio_trx(
    invoice_name,
    folio,
    amount,
    type,
    ftb_doc,
    remark,
    index,
    debit_account=None,
    credit_account=None,
):
    if credit_account is None:
        credit_account = frappe.get_value(
            "Inn Folio Transaction Type",
            filters={"name": type},
            fieldname="credit_account",
        )
    if debit_account is None:
        debit_account = frappe.get_value(
            "Inn Folio Transaction Type",
            filters={"name": type},
            fieldname="debit_account",
        )

    # Create Inn Folio Transaction
    new_doc = frappe.new_doc("Inn Folio Transaction")
    new_doc.flag = "Debit"
    new_doc.is_void = 0
    new_doc.idx = index
    new_doc.transaction_type = type
    new_doc.amount = amount
    new_doc.reference_id = invoice_name
    new_doc.debit_account = debit_account
    new_doc.credit_account = credit_account
    new_doc.remark = remark
    new_doc.parent = folio
    new_doc.parenttype = "Inn Folio"
    new_doc.parentfield = "folio_transaction"
    new_doc.ftb_id = ftb_doc.name
    new_doc.insert()

    # Create Inn Folio Transaction Bundle Detail
    ftbd_doc = frappe.new_doc("Inn Folio Transaction Bundle Detail")
    ftbd_doc.transaction_type = new_doc.transaction_type
    ftbd_doc.transaction_id = new_doc.name
    ftb_doc.append("transaction_detail", ftbd_doc)


def remove_pos_invoice_bill(invoice_name: str, folio_name: str):
    pos_invoice = frappe.get_doc("POS Invoice", invoice_name)
    for payment in pos_invoice.payments:
        frappe.db.set_value("Sales Invoice Payment", payment.name, "amount", 0)
        frappe.db.set_value("Sales Invoice Payment", payment.name, "base_amount", 0)

    frappe.db.set_value("POS Invoice", invoice_name, "status", "Transferred")
    frappe.db.set_value("POS Invoice", invoice_name, "grand_total", 0)
    frappe.db.set_value("POS Invoice", invoice_name, "rounded_total", 0)
    frappe.db.set_value("POS Invoice", invoice_name, "in_words", 0)
    frappe.db.set_value("POS Invoice", invoice_name, "paid_amount", 0)
    frappe.db.set_value(
        "POS Invoice",
        invoice_name,
        "consolidated_invoice",
        f"Transferred to {folio_name}",
    )
    frappe.db.set_value("POS Invoice", invoice_name, "status", "Consolidated")
    
@frappe.whitelist()
def transfer_charge_to_customer(cart_data_str, paying_customer,pos_profile_name, original_customer=None):
    try:
        cart_data = json.loads(cart_data_str)
        items_to_issue = cart_data.get("items", [])
        invoice = frappe._dict(cart_data_str) if isinstance(cart_data_str, dict) else json.loads(cart_data_str)
        invoice_name = invoice.get("name")
        grand_total = flt(invoice.get("grand_total"))
        company = invoice.get("company")
        posting_date = get_datetime(invoice.get("posting_date")).date()
        if not all([len(items_to_issue) > 0, grand_total > 0, company, paying_customer, pos_profile_name]):
            frappe.throw(_("Missing required data for customer charge transfer."))
        if not all([invoice_name, grand_total > 0, company, paying_customer]):
            frappe.throw(_("Missing required data: Invoice Name, Grand Total, Company, or Paying Customer."))

        # 1. جلب حساب "Customer Charge Account" من الإعدادات
        customer_charge_settings_doctype = "Inn Hotels Setting"
        customer_charge_account_field = "customer_charge_account"

        charge_transfer_account = frappe.db.get_single_value(customer_charge_settings_doctype, customer_charge_account_field)
        if not charge_transfer_account:
            frappe.throw(_("Customer Charge Transfer Account is not set in {0}.").format(customer_charge_settings_doctype))

        # 2. جلب الحساب المدين للعميل الدافع (Paying Customer)
        paying_customer_doc = frappe.get_doc("Customer", paying_customer)
        customer_receivable_account = paying_customer_doc.get("receivable_account")
        if not customer_receivable_account:
            # كحل بديل، جلب الحساب الافتراضي للذمم المدينة من الشركة
            customer_receivable_account = frappe.get_cached_value('Company', company, 'default_receivable_account')
            if not customer_receivable_account:
                 frappe.throw(_("Receivable account for paying customer {0} not found, and no default set for company {1}.").format(paying_customer, company))

        # 3. إنشاء قيد يومية (Journal Entry)        
        je = frappe.new_doc("Journal Entry")
        je.voucher_type = "Journal Entry"
        je.posting_date = posting_date
        je.company = company
        je.user_remark = _("Transfer of POS Invoice {0} charge (originally for {1}) to customer {2}.")\
            .format(invoice_name, original_customer or _("Walk-in"), paying_customer)

        # الطرف المدين: حساب العميل الدافع       
        je.append("accounts", {
            "account": customer_receivable_account,
            "party_type": "Customer",
            "party": paying_customer,
            "debit_in_account_currency": grand_total,
            "cost_center": invoice.get("cost_center") 
        })

        # الطرف الدائن: حساب تحويل رسوم العملاء        
        je.append("accounts", {
            "account": charge_transfer_account,
            "credit_in_account_currency": grand_total,
            "cost_center": invoice.get("cost_center")
        })

        je.flags.ignore_mandatory = True
        je.submit()
        
        items_to_issue = cart_data.get("items", [])
        se_items_list = []
        for cart_item in items_to_issue:
            se_items_list.append({
                "item_code": cart_item.get("item_code"),
                "qty": cart_item.get("qty"),
                "uom": cart_item.get("uom"),
                "stock_uom": cart_item.get("stock_uom"),
                "conversion_factor": cart_item.get("conversion_factor"),
                "basic_rate": cart_item.get("rate"),
            })
        create_material_issue_from_pos(pos_profile_name, se_items_list)
        return {
            "status": "success",
            "journal_entry": je.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "transfer_charge_to_customer Error")
        return {
            "status": "error",
            "error": str(e)
        }
        
def create_material_issue_from_pos(pos_profile_name, items_list,folio_name=None):
    """
    Creates a Material Issue (Stock Entry) based on a POS Profile using a detailed
    items list. It fetches the warehouse from the POS Profile and issues only
    stockable items, using all provided item details like UOM and rate.
    """
    ignored_items = []
    stock_items_to_add = []

    try:
        # الخطوة 1: التحقق من ملف نقطة البيع واستخراج المخزن والشركة
        if not frappe.db.exists("POS Profile", pos_profile_name):
            return {"status": "error", "message": _("POS Profile '{0}' not found.").format(pos_profile_name)}

        pos_data = frappe.get_value("POS Profile", pos_profile_name, ["warehouse", "company"], as_dict=True)
        if not pos_data:
             return {"status": "error", "message": _("Could not retrieve data for POS Profile '{0}'.").format(pos_profile_name)}

        source_warehouse =  pos_data.warehouse
        company =  pos_data.company

        if not source_warehouse:
            return {"status": "error", "message": _("Warehouse is not set in POS Profile '{0}'.").format(pos_profile_name)}
        # الخطوة 2: فلترة الأصناف واستخدام البيانات التفصيلية
        for item_data in items_list:
            item_code = item_data.get("item_code")
            if not item_code or not item_data.get("qty"):
                frappe.log_error(f"Skipping invalid item entry: {item_data}", "Material Issue Creation from POS")
                continue

            # التحقق إذا كان الصنف مخزنيًا
            is_stock_item = frappe.get_value("Item", item_code, "is_stock_item")
            if is_stock_item:
                item_data['s_warehouse'] = source_warehouse
                stock_items_to_add.append(item_data)
            else:
                ignored_items.append(item_code)
        if not stock_items_to_add:
            return {
                "status": "warning",
                "message": _("No stockable items found in the provided list."),
                "doc_name": None,
                "ignored_items": ignored_items
            }

        # الخطوة 3: إنشاء وإعتماد إدخال المخزون
        se = frappe.new_doc("Stock Entry")
        se.purpose = "Material Issue"
        se.stock_entry_type = "Material Issue"
        se.set_posting_time = 1
        se.company = company
        se.custom_from_pos= 1
        se.custom_folio = folio_name
        
        if hasattr(se, 'from_warehouse'):
             se.from_warehouse = source_warehouse

        for item in stock_items_to_add:
            se.append("items", item)

        se.insert(ignore_permissions=True)
        se.submit()

        return {
            "status": "success",
            "message": _("Material Issue {0} created successfully from POS Profile '{1}'.").format(se.name, pos_profile_name),
            "doc_name": se.name,
            "ignored_items": ignored_items
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Material Issue Creation from POS Failed")
        frappe.db.rollback()
        return {
            "status": "error",
            "message": str(e),
            "doc_name": None,
            "ignored_items": ignored_items
        }