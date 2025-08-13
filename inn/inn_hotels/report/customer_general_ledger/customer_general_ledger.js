// Copyright (c) 2025, Core Initiative and contributors
// For license information, please see license.txt

frappe.query_reports["Customer General Ledger"] = {
    "filters": [
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
            "fieldname": "account",
            "label": __("Account"),
            "fieldtype": "Link",
            "options": "Account"
        },
        {
            "fieldname": "customer",
            "label": __("Customer"),
            "fieldtype": "Link",
            "options": "Customer"
        },
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "default": frappe.defaults.get_user_default("Company")
        },
    ],  // Fixed: Added comma here to separate filters from formatter
    formatter: function (value, row, column, data, default_formatter) {
        let iconHTML = '';
        let color = '#333'; // default color
    
        switch (column.fieldname) {
            case "against_account":
                iconHTML = `<i class="fa fa-barcode" style="color: #2196F3;"></i>`;
                color = '#2196F3';
                break;
            case "voucher_no":
                iconHTML = `<i class="fa fa-tag" style="color: #4CAF50;"></i>`;
                color = '#4CAF50';
                break;
            case "account":
                iconHTML = `<i class="fa fa-barcode" style="color: #2196F3;"></i>`;
                color = '#2196F3';
                break;
            case "voucher_type":
                iconHTML = `<i class="fa fa-file-invoice" style="color: #FF9800;"></i>`;
                color = '#FF9800';
                break;
            case "debit":
                iconHTML = `<i class="fa fa-arrow-down" style="color: #009688;"></i>`;
                color = '#009688';
                break;
            case "credit":
                iconHTML = `<i class="fa fa-arrow-up" style="color: #F44336;"></i>`;
                color = '#F44336';
                break;
            case "balance":
                iconHTML = `<i class="fa fa-balance-scale" style="color: #9C27B0;"></i>`;
                color = '#9C27B0';
                break;
            case "posting_date":
                iconHTML = `<i class="fa fa-calendar" style="color: #3F51B5;"></i>`; 
                color = '#3F51B5';
                break;                                        
            default:
                return default_formatter(value, row, column, data);
            
        }
        return `
            <div style="display: flex; align-items: center; gap: 8px; color: ${color}">
                ${iconHTML}
                ${default_formatter(value, row, column, data)}
            </div>
        `;
    }
};