// Copyright (c) 2025, Core Initiative and contributors
// For license information, please see license.txt

frappe.query_reports["Customer General Ledger Summary"] = {
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
    ],
    "onload": function(report) {
        if (!report.custom_style_added) {
            const style = document.createElement("style");
            style.innerHTML = `
                /* General table styling for a cleaner look */
                .frappe-list-table {
                    border-collapse: separate;
                    border-spacing: 0 8px; /* Adds space between rows */
                }
                .frappe-list-table > tbody > tr {
                    background-color: var(--fg-color); /* Use Frappe's foreground color for rows */
                    box-shadow: 0 2px 5px rgba(0,0,0,0.05); /* Subtle shadow for depth */
                    border-radius: 8px; /* Rounded corners for rows */
                    transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
                }
                .frappe-list-table > tbody > tr:hover {
                    transform: translateY(-2px); /* Slight lift on hover */
                    box-shadow: 0 4px 10px rgba(0,0,0,0.1); /* Enhanced shadow on hover */
                }
                .frappe-list-table > tbody > tr > td {
                    border: none !important; /* Remove individual cell borders */
                    padding: 12px 15px; /* More padding */
                }
                .frappe-list-table > thead > tr > th {
                    border-bottom: 2px solid var(--border-color); /* Stronger header border */
                    padding: 12px 15px;
                    background-color: var(--bg-color); /* Frappe's background color for header */
                    font-weight: 600; /* Bolder header text */
                    color: var(--text-color);
                }

                /* Styling for icons within cells */
                .report-icon {
                    margin-right: 8px;
                    opacity: 0.8; 
                }

                /* Specific styling for the totals row */
                .dt-cell__customer .total-row-label {
                    font-weight: bold;
                    font-size: 1.1em;
                }
            `;
            document.head.appendChild(style);
            report.custom_style_added = true;
        }
    },
    "formatter": function (value, row, column, data, default_formatter) {
        let iconHTML = '';
        let color_for_text = '';
        switch (column.fieldname) {
            case "customer":
                iconHTML = `<i class="fa fa-user report-icon" style="color: #0984E3;"></i>`; 
                break;
            case "total_debit":
                iconHTML = `<i class="fa fa-arrow-down report-icon" style="color: #2196F3;"></i>`;
                color_for_text = '#2196F3';
                break;
            case "total_credit":
                iconHTML = `<i class="fa fa-arrow-up report-icon" style="color: #F44336;"></i>`;
                color_for_text = '#F44336';
                break;
            case "balance":
                iconHTML = `<i class="fa fa-balance-scale report-icon" style="color: #9C27B0;"></i>`;
                break;
            default:
                return default_formatter(value, row, column, data);
        }

        const numeric_value = parseFloat(value); 
        if (isNaN(numeric_value)) {
        } else if (column.fieldname === "balance") {
            if (numeric_value > 0) {
                color_for_text = 'green'; 
            } else if (numeric_value < 0) {
                color_for_text = 'red'; 
            } else {
                color_for_text = 'gray'; 
            }
        }

        let base_formatted_value = default_formatter(value, row, column, data);

        let final_cell_html = `
            <div style="display: flex; align-items: center; gap: 8px; color: ${color_for_text || 'inherit'};">
                ${iconHTML}
                ${base_formatted_value}
            </div>
        `;

        if (column.fieldname === "customer") {
            if (row.is_total) {
                final_cell_html = `<span class="total-row-label">${final_cell_html}</span>`; 
            } else {
                final_cell_html = `<span style="font-weight: bold;">${final_cell_html}</span>`; 
            }
        }

        if (["total_debit", "total_credit", "balance"].includes(column.fieldname)) {
            final_cell_html = `<div style="text-align: right;">${final_cell_html}</div>`;

            if (row.is_total) {
                final_cell_html = `
                    <div style="font-weight: bold; background-color: var(--extra-light-blue); padding: 5px 15px; border-radius: 4px;">
                        ${final_cell_html}
                    </div>
                `;
            }
        }
        
        return final_cell_html;
    }
};
