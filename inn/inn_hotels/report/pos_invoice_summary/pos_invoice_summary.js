// Copyright (c) 2025, Core Initiative and contributors
// For license information, please see license.txt

frappe.query_reports["POS Invoice Summary"] = {
	"filters": [
		{
			"fieldname": "customer_name",
			"label": __("Customer Name"),
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"fieldname": "invoice_number",
			"label": __("Invoice Number"),
			"fieldtype": "Link",
			"options": "POS Invoice"
		},
		// {
		// 	"fieldname": "room_number",
		// 	"label": __("Room Number"),
		// 	"fieldtype": "Link",
		// 	"options": "Inn Room",
		// 	"description": __("Filter by the room associated with the reservation linked to the POS Invoice.")
		// },
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			"reqd": 1
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
		{
			"fieldname": "payment_method",
			"label": __("Payment Method"),
			"fieldtype": "Link",
			"options": "Mode of Payment"
		},
		{
			"fieldname": "invoice_creator",
			"label": __("Invoice Creator"),
			"fieldtype": "Link",
			"options": "User"
		}
	],

    formatter: function(value, row, column, data, default_formatter) {
        let formatted_value = default_formatter(value, row, column, data);

        let icon_html = '';
        switch(column.fieldname) {
            case 'employee_name':
                icon_html = '<i class="fa fa-briefcase report-icon" style="color: #6C5CE7;"></i>';
                break;
            case 'customer_name':
                icon_html = '<i class="fa fa-user report-icon" style="color: #0984E3;"></i>';
                break;
            case 'invoice_name':
                icon_html = '<i class="fa fa-file-invoice report-icon" style="color: #D63031;"></i>';
                break;
            case 'pos_profile':
                icon_html = '<i class="fa fa-store report-icon" style="color: #FDCB6E;"></i>';
                break;
            case 'posting_date':
                icon_html = '<i class="fa fa-calendar-alt report-icon" style="color: #636E72;"></i>';
                break;
            case 'posting_time':
                icon_html = '<i class="fa fa-clock report-icon" style="color: #B2BEC3;"></i>';
                break;
        }
        let final_html = icon_html + formatted_value;
        
        return final_html;
    },
};