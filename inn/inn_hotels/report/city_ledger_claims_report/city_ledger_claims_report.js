// Copyright (c) 2025, Core Initiative and contributors
// For license information, please see license.txt

frappe.query_reports["City Ledger Claims Report"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "default": frappe.defaults.get_user_default("Company")
        },
        {
            "fieldname": "customer",
            "label": __("Customer"),
            "fieldtype": "Link",
            "options": "Customer"
        },
    ],
        formatter: function (value, row, column, data, default_formatter) {
        let iconHTML = '';
        let color = '#333'; // default color
    
        switch (column.fieldname) {
            case "customer":
                iconHTML = `<i class="fa fa-user" style="color: #3F51B5;"></i>`;
                color = '#3F51B5';
                break;
            case "total_amount":
                iconHTML = `<i class="fa fa-money" style="color: #4CAF50;""></i>`;
                color = '#4CAF50';
                break;
            case "total_claimed":
                iconHTML = `<i class="fa fa-handshake-o" style="color: #FF9800;""></i>`;
                color = '#FF9800';
                break;
            case "total_received":
                iconHTML = `<i class="fa fa-check-circle" style="color: #009688;"></i>`;
                color = '#009688';
                break;
            case "outstanding":
                iconHTML = `<i class="fa fa-exclamation-triangle" style="color: #F44336;"></i>`;
                color = '#F44336';
                break;
            case "left_to_claim":
                iconHTML = `<i class="fa fa-clock-o" style="color: #9C27B0;""></i>`;
                color = '#9C27B0';
                break;
            
        }
        return `
            <div style="display: flex; align-items: center; gap: 8px; color: ${color}">
                ${iconHTML}
                ${default_formatter(value, row, column, data)}
            </div>
        `;
    }
};