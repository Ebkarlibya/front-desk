# -*- coding: utf-8 -*-
# Copyright (c) 2020, Core Initiative and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import json
from pathlib import Path
import frappe
from frappe.model.document import Document


class InnPointOfSaleTable(Document):
    pass

@frappe.whitelist()
def get_table_status(table_id):
    table = frappe.get_doc("Inn Point of Sale Table", table_id)
    return table.status

@frappe.whitelist()
def update_table_status(table_id, status):
    table = frappe.get_doc("Inn Point of Sale Table", table_id)
    table.status = status
    table.save()
    frappe.msgprint(_("Table status updated successfully."))


def generate_table():
    # not used, why develop specific function when user already can create by themself?
    file_loc = Path(__file__).with_name("table_data.json")
    with file_loc.open("r") as file:
        data = json.load(file)
        file.close()

    for table_name in data.table_name:
        if frappe.db.exists("Inn Point of Sale Table", table_name):
            frappe.msgprint(
                _("Table with {0} already exists").format(table_name), indicator="yellow")
            continue

        doc = frappe.new_doc("Inn Point of Sale Table")
        doc.table_name = table_name
        doc.status = "Empty"
        doc.insert()
