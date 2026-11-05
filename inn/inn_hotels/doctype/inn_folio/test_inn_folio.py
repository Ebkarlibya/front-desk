# -*- coding: utf-8 -*-
# Copyright (c) 2020, Core Initiative and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from inn.inn_hotels.doctype.inn_folio.inn_folio import (
    update_balance,
    close_folio,
    credit_excess_to_customer,
)
from inn.inn_hotels.doctype.inn_folio_transaction.inn_folio_transaction import (
    add_charge,
    add_payment,
)


class TestInnFolio(FrappeTestCase):
    def setUp(self):
        self.debit_type = self.get_trx_type("Debit")
        self.credit_type = self.get_trx_type("Credit")
        self.mode_of_payment = "Cash"
        self.customer = self.get_any("Customer")
        self.group = self.get_any("Inn Group")
        self.folio = self.make_folio()

    # ---------- helpers ----------
    def get_trx_type(self, flag):
        name = frappe.db.get_value(
            "Inn Folio Transaction Type", {"type": flag, "is_included": 1}, "name"
        )
        if not name:
            self.skipTest("No Inn Folio Transaction Type with type=%s" % flag)
        return name

    def get_any(self, doctype):
        name = frappe.db.get_value(doctype, {}, "name")
        if not name:
            self.skipTest("No %s record in the site" % doctype)
        return name

    def make_folio(self):
        folio = frappe.new_doc("Inn Folio")
        folio.type = "Master"
        folio.customer_id = self.customer
        folio.group_id = self.group
        folio.open = frappe.utils.today()
        folio.close = frappe.utils.add_days(frappe.utils.today(), 1)
        folio.insert()
        return folio

    def charge(self, amount):
        add_charge(self.debit_type, amount, "A", "test charge", self.folio.name)

    def pay(self, amount):
        add_payment(
            self.credit_type,
            amount,
            self.mode_of_payment,
            "A",
            "test payment",
            self.folio.name,
        )

    def payment_entries_count(self):
        
        return frappe.db.count(
            "Payment Entry", {"party": self.customer, "docstatus": 1}
        )

    # ---------- tests ----------
    def test_excess_is_calculated(self):
        self.charge(1000)
        self.pay(3000)
        update_balance(self.folio.name)
        self.folio.reload()
        self.assertEqual(flt(self.folio.excess_amount), 2000)

    def test_no_excess_when_balance_negative(self):
        self.charge(3000)
        self.pay(1000)
        update_balance(self.folio.name)
        self.folio.reload()
        self.assertEqual(flt(self.folio.excess_amount), 0)

    def test_close_blocked_on_negative_balance(self):
        self.charge(3000)
        self.pay(1000)
        before = self.payment_entries_count()
        result = close_folio(self.folio.name)
        self.folio.reload()
        self.assertNotEqual(self.folio.status, "Closed")
        self.assertIn("negative", result)
        self.assertEqual(self.payment_entries_count() - before, 0)

    def test_close_with_zero_balance_creates_no_payment_entry(self):
        self.charge(1000)
        self.pay(1000)
        before = self.payment_entries_count()
        close_folio(self.folio.name)
        self.folio.reload()
        self.assertEqual(self.folio.status, "Closed")
        self.assertEqual(self.payment_entries_count() - before, 0)

    def test_close_keeps_excess_and_zeroes_balance(self):
        self.charge(1000)
        self.pay(3000)
        before = self.payment_entries_count()
        close_folio(self.folio.name)
        self.folio.reload()
        self.assertEqual(self.folio.status, "Closed")
        self.assertEqual(flt(self.folio.excess_amount), 2000)
        self.assertEqual(flt(self.folio.excess_credited), 2000)
        self.assertEqual(flt(self.folio.balance), 0)
        self.assertEqual(self.payment_entries_count() - before, 1)

    def test_excess_not_credited_twice(self):
        self.charge(1000)
        self.pay(3000)
        close_folio(self.folio.name)
        after_close = self.payment_entries_count()
        credit_excess_to_customer(self.folio.name)
        self.assertEqual(self.payment_entries_count(), after_close)

    def test_closed_folio_keeps_values_after_update_balance(self):
        self.charge(1000)
        self.pay(3000)
        close_folio(self.folio.name)
        update_balance(self.folio.name)
        self.folio.reload()
        self.assertEqual(flt(self.folio.balance), 0)
        self.assertEqual(flt(self.folio.excess_amount), 2000)