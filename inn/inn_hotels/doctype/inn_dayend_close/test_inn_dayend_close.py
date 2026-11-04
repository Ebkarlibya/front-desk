# -*- coding: utf-8 -*-
# Copyright (c) 2020, Core Initiative and Contributors
# See license.txt

import datetime
from unittest.mock import MagicMock, patch

import inn.inn_hotels.doctype.inn_dayend_close.inn_dayend_close as dayend_close

from frappe.tests.utils import FrappeTestCase


class TestInnDayendClose(FrappeTestCase):

    def test_dayend_close_calls_credit_today_closed_folios(self):
        settings = MagicMock()
        settings.include_tax = 0

        dayend_doc = MagicMock()
        dayend_doc.status = "Open"

        audit_log = MagicMock()

        with patch.object(
            dayend_close.frappe,
            "get_doc",
            side_effect=[settings, dayend_doc],
        ), patch.object(
            dayend_close.frappe,
            "get_all",
            return_value=[],
        ), patch.object(
            dayend_close.frappe,
            "new_doc",
            return_value=audit_log,
        ), patch.object(
            dayend_close,
            "get_last_audit_date",
            return_value=datetime.date.today(),
        ), patch.object(
            dayend_close,
            "credit_today_closed_folios",
        ) as mock_credit:

            result = dayend_close.process_dayend_close("TEST-DAYEND")

            mock_credit.assert_called_once()
            self.assertEqual(result, "Closed")
            audit_log.insert.assert_called_once()
            dayend_doc.save.assert_called_once()