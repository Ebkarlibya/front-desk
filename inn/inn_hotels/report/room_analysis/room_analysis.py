# Copyright (c) 2025, Core Initiative and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		{
			"label": _("Room Name"),
			"fieldname": "room_name",
			"fieldtype": "Link",
			"options": "Inn Room",
			"width": 150
		},
		{
			"label": _("Room Type"),
			"fieldname": "room_type",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": _("Check-ins"),
			"fieldname": "check_in_count",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": _("Check-outs"),
			"fieldname": "check_out_count",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": _("Total Activities"),
			"fieldname": "total_activity",
			"fieldtype": "Int",
			"width": 130
		}
	]

def get_data(filters):
	conditions = ""
	if filters.get("room_name"):
		conditions += " AND room_id = %(room_name)s"
	if filters.get("from_date"):
		conditions += " AND start >= %(from_date)s"
	if filters.get("to_date"):
		conditions += " AND end <= %(to_date)s"

	query = f"""
		SELECT
			room_id AS room_name,
			(SELECT room_type FROM `tabInn Room` WHERE name = room_id) AS room_type,
			SUM(CASE WHEN status = 'Booked' THEN 1 ELSE 0 END) AS check_in_count,
			SUM(CASE WHEN status = 'Finished' THEN 1 ELSE 0 END) AS check_out_count
		FROM `tabInn Room Booking`
		WHERE 1=1 {conditions}
		GROUP BY room_id
	"""

	raw_data = frappe.db.sql(query, filters, as_dict=True)

	# إضافة مجموع الدخول والخروج
	for row in raw_data:
		row["total_activity"] = (row.get("check_in_count") or 0) + (row.get("check_out_count") or 0)

	return raw_data
