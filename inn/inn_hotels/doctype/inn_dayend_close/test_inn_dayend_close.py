# -*- coding: utf-8 -*-
# Copyright (c) 2020, Core Initiative and Contributors
# See license.txt
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import frappe
import datetime

from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from inn.inn_hotels.doctype.inn_dayend_close.inn_dayend_close import (
    credit_today_closed_folios,
)


class TestInnDayendClose(FrappeTestCase):

    def setUp(self):
        self.customer = self.get_any("Customer")
        self.group = self.get_any("Inn Group")
        self.folio = self.make_folio()

    # ---------- helpers ----------

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
        folio.open = datetime.date.today()
        folio.close = datetime.date.today()
        folio.status = "Closed"
        folio.excess_amount = 2000
        folio.excess_credited = 0
        folio.balance = 0
        folio.insert()

        return folio

    def payment_entries_count(self):
        return frappe.db.count(
            "Payment Entry",
            {
                "party": self.customer,
                "docstatus": 1,
            },
        )

    # ---------- tests ----------

    def test_today_closed_folio_credits_excess(self):
        before = self.payment_entries_count()

        credit_today_closed_folios()

        self.folio.reload()

        self.assertEqual(
            flt(self.folio.excess_credited),
            2000,
        )

        self.assertEqual(
            self.payment_entries_count() - before,
            1,
        )

    def test_excess_is_not_credited_twice(self):
        credit_today_closed_folios()

        after_first_call = self.payment_entries_count()

        credit_today_closed_folios()

        self.assertEqual(
            self.payment_entries_count(),
            after_first_call,
        )

    def test_folio_closed_on_another_date_is_not_credited(self):
        self.folio.close = datetime.date.today() - datetime.timedelta(days=1)
        self.folio.save()

        before = self.payment_entries_count()

        credit_today_closed_folios()

        self.folio.reload()

        self.assertEqual(
            flt(self.folio.excess_credited),
            0,
        )

        self.assertEqual(
            self.payment_entries_count(),
            before,
        )
