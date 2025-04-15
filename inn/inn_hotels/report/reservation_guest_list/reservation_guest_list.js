frappe.require("assets/frappe/css/frappe-theme.css", () => {
	const style = document.createElement("style");
	style.innerHTML = `
		.tree-toggle {
			display: inline-block;
			margin-right: 6px;
			transition: transform 0.3s ease;
		}
		.tree-toggle.expanded {
			transform: rotate(90deg);
		}
		.tree-toggle.collapsed {
			transform: rotate(0deg);
		}
	`;
	document.head.appendChild(style);
});
frappe.query_reports["Reservation Guest List"] = {
	"filters": [
		{
			"fieldname": "reservation",
			"label": __("Reservation"),
			"fieldtype": "Link",
			"options": "Inn Reservation"
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date"
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date"
		}
	],

"formatter": function(value, row, column, data, default_formatter) {
	value = default_formatter(value, row, column, data);

	const has_value = value && value !== "null" && value !== "undefined" && value.trim() !== "";
	if (!has_value) return "";

	// ⬅️ أيقونة السهم للطي/الفك
	let toggle_icon = "";
	if (data.is_group && column.fieldname === "reservation") {
		let icon_class = data.expanded ? "expanded" : "collapsed";
		toggle_icon = `<span class="tree-toggle ${icon_class}">▶</span>`;
		value = toggle_icon + " " + value;
	}

	// 🧠 أيقونات الأعمدة حسب نوعها
	if (column.fieldname === "room") {
		value = `<i class="fa fa-bed" style="margin-right:5px;"></i>` + value;
	} else if (column.fieldname === "reservation") {
		value = `<i class="fa fa-calendar" style="margin-right:5px;"></i>` + value;
	} else if (column.fieldname === "customer") {
		value = `<i class="fa fa-user" style="margin-right:5px;"></i>` + value;
	} else if (column.fieldname === "guest_name") {
		value = `<i class="fa fa-child" style="margin-right:5px;"></i>` + value;
	} else if (column.fieldname === "passport_number") {
		value = `<i class="fa fa-id-card" style="margin-right:5px;"></i>` + value;
	} else if (column.fieldname === "nationality") {
		value = `<i class="fa fa-flag" style="margin-right:5px;"></i>` + value;
	} else if (column.fieldname === "status") {
		value = `<i class="fa fa-circle" style="margin-right:5px; color:#5bc0de;"></i>` + value;
	} else if (column.fieldname === "type") {
		value = `<i class="fa fa-tag" style="margin-right:5px;"></i>` + value;
	} else if (column.fieldname === "expected_arrival") {
		value = `<i class="fa fa-sign-in" style="margin-right:5px;"></i>` + value;
	} else if (column.fieldname === "expected_departure") {
		value = `<i class="fa fa-sign-out" style="margin-right:5px;"></i>` + value;
	}

	// تلوين الصف الأب والابن
	if (data.is_group) {
		value = `<span style="background: #5cb85c; color: #fff; padding: 3px 5px; border-radius: 3px;">${value}</span>`;
	} else if (data.indent) {
		value = `<span style="background: #d9edf7; color: #000; padding: 3px 5px; border-radius: 3px;">${value}</span>`;
	}

	return value;
}

};
