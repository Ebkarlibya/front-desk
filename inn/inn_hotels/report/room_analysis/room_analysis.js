// Copyright (c) 2025, Core Initiative and contributors
// For license information, please see license.txt

frappe.query_reports["Room Analysis"] = {
	"filters": [
		{
			"fieldname": "room_name",
			"label": __("Room Name"),
			"fieldtype": "Link",
			"options": "Inn Room",
			"default": ""
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today()
		}
	],
	formatter: function (value, row, column, data, default_formatter) {
		let iconHTML = "";
		value = default_formatter(value, row, column, data);

		// تخصيص الأيقونات باللون الأخضر
		switch (column.fieldname) {
			case "room_name":
				iconHTML = `<i class="fa fa-bed" style="margin-right: 5px; color: green;"></i>`;
				break;
			case "room_type":
				iconHTML = `<i class="fa fa-building" style="margin-right: 5px; color: green;"></i>`;
				break;
		}

		return iconHTML + value;
	}
};
