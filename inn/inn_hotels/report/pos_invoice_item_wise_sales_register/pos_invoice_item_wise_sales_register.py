# Copyright (c) 2025, Core Initiative and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder import functions as fn
from frappe import _ 


def execute(filters=None):
	columns, data = [], []
	data = get_items(filters,additional_query_columns=None,additional_conditions=None)
	columns = get_columns(additional_table_columns=None,filters=filters)
	return columns, data



def get_columns(additional_table_columns, filters):
	columns = []

	if filters.get("group_by") != ("Item"):
		columns.extend(
			[
				{
					"label": _("Item Code"),
					"fieldname": "item_code",
					"fieldtype": "Link",
					"options": "Item",
					"width": 120,
				},
				{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 120},
			]
		)

	if filters.get("group_by") not in ("Item", "Item Group"):
		columns.extend(
			[
				{
					"label": _("Item Group"),
					"fieldname": "item_group",
					"fieldtype": "Link",
					"options": "Item Group",
					"width": 120,
				}
			]
		)

	columns.extend(
		[
			{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 150},
			{
				"label": _("Invoice"),
				"fieldname": "invoice",
				"fieldtype": "Link",
				"options": "Sales Invoice",
				"width": 150,
			},
			{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
		]
	)

	if filters.get("group_by") != "Customer":
		columns.extend(
			[
				{
					"label": _("Customer Group"),
					"fieldname": "customer_group",
					"fieldtype": "Link",
					"options": "Customer Group",
					"width": 120,
				}
			]
		)

	if filters.get("group_by") not in ("Customer", "Customer Group"):
		columns.extend(
			[
				{
					"label": _("Customer"),
					"fieldname": "customer",
					"fieldtype": "Link",
					"options": "Customer",
					"width": 120,
				},
				{
					"label": _("Customer Name"),
					"fieldname": "customer_name",
					"fieldtype": "Data",
					"width": 120,
				},
			]
		)

	if additional_table_columns:
		columns += additional_table_columns

	columns += [
		{
			"label": _("Receivable Account"),
			"fieldname": "debit_to",
			"fieldtype": "Link",
			"options": "Account",
			"width": 80,
		},
		{
			"label": _("Mode Of Payment"),
			"fieldname": "mode_of_payment",
			"fieldtype": "Data",
			"width": 120,
		},
	]

	if filters.get("group_by") != "Territory":
		columns.extend(
			[
				{
					"label": _("Territory"),
					"fieldname": "territory",
					"fieldtype": "Link",
					"options": "Territory",
					"width": 80,
				}
			]
		)

	columns += [
		{
			"label": _("Project"),
			"fieldname": "project",
			"fieldtype": "Link",
			"options": "Project",
			"width": 80,
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 80,
		},
		{
			"label": _("Sales Order"),
			"fieldname": "sales_order",
			"fieldtype": "Link",
			"options": "Sales Order",
			"width": 100,
		},
		{
			"label": _("Delivery Note"),
			"fieldname": "delivery_note",
			"fieldtype": "Link",
			"options": "Delivery Note",
			"width": 100,
		},
		{
			"label": _("Income Account"),
			"fieldname": "income_account",
			"fieldtype": "Link",
			"options": "Account",
			"width": 100,
		},
		{
			"label": _("Cost Center"),
			"fieldname": "cost_center",
			"fieldtype": "Link",
			"options": "Cost Center",
			"width": 100,
		},
		{"label": _("Stock Qty"), "fieldname": "stock_qty", "fieldtype": "Float", "width": 100},
		{
			"label": _("Stock UOM"),
			"fieldname": "stock_uom",
			"fieldtype": "Link",
			"options": "UOM",
			"width": 100,
		},
		{
			"label": _("Rate"),
			"fieldname": "rate",
			"fieldtype": "Float",
			"options": "currency",
			"width": 100,
		},
		{
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 100,
		},
	]

	if filters.get("group_by"):
		columns.append(
			{"label": _("% Of Grand Total"), "fieldname": "percent_gt", "fieldtype": "Float", "width": 80}
		)

	return columns

def apply_conditions(query, pi, pii, pip, filters, additional_conditions=None):
	for opts in ("company", "customer"):
		if filters.get(opts):
			query = query.where(pi[opts] == filters[opts])

	if filters.get("from_date"):
		query = query.where(pi.posting_date >= filters.get("from_date"))

	if filters.get("to_date"):
		query = query.where(pi.posting_date <= filters.get("to_date"))

	if filters.get("mode_of_payment"):
		subquery = (
			frappe.qb.from_(pip)
			.select(pip.parent)
			.where(pip.mode_of_payment == filters.get("mode_of_payment"))
			.groupby(pip.parent)
		)
		query = query.where(pi.name.isin(subquery))

	if filters.get("warehouse"):
		if frappe.db.get_value("Warehouse", filters.get("warehouse"), "is_group"):
			lft, rgt = frappe.db.get_all(
				"Warehouse", filters={"name": filters.get("warehouse")}, fields=["lft", "rgt"], as_list=True
			)[0]
			warehouses = frappe.db.get_all("Warehouse", {"lft": (">", lft), "rgt": ("<", rgt)}, pluck="name")
			query = query.where(pii.warehouse.isin(warehouses))
		else:
			query = query.where(pii.warehouse == filters.get("warehouse"))

	if filters.get("brand"):
		query = query.where(pii.brand == filters.get("brand"))

	if filters.get("item_code"):
		query = query.where(pii.item_code == filters.get("item_code"))

	if filters.get("item_group"):
		if frappe.db.get_value("Item Group", filters.get("item_group"), "is_group"):
			item_groups = get_descendants_of("Item Group", filters.get("item_group"))
			item_groups.append(filters.get("item_group"))
			query = query.where(pii.item_group.isin(item_groups))
		else:
			query = query.where(pii.item_group == filters.get("item_group"))

	if filters.get("income_account"):
		query = query.where(
			(pii.income_account == filters.get("income_account"))
			| (pii.deferred_revenue_account == filters.get("income_account"))
			| (pi.unrealized_profit_loss_account == filters.get("income_account"))
		)

	for key, value in (additional_conditions or {}).items():
		query = query.where(pi[key] == value)

	return query


def apply_order_by_conditions(doctype, query, filters):
	invoice = f"`tab{doctype}`"
	invoice_item = f"`tab{doctype} Item`"

	if not filters.get("group_by"):
		query += f" order by {invoice}.posting_date desc, {invoice_item}.item_group desc"
	elif filters.get("group_by") == "Invoice":
		query += f" order by {invoice_item}.parent desc"
	elif filters.get("group_by") == "Item":
		query += f" order by {invoice_item}.item_code"
	elif filters.get("group_by") == "Item Group":
		query += f" order by {invoice_item}.item_group"
	elif filters.get("group_by") in ("Customer", "Customer Group", "Territory", "Supplier"):
		filter_field = frappe.scrub(filters.get("group_by"))
		query += f" order by {filter_field} desc"

	return query


def get_items(filters, additional_query_columns, additional_conditions=None):
	doctype = "POS Invoice"
	pi = frappe.qb.DocType("POS Invoice")
	pii = frappe.qb.DocType("POS Invoice Item")
	pip = frappe.qb.DocType("Sales Invoice Payment")
	item = frappe.qb.DocType("Item")

	query = (
		frappe.qb.from_(pi)
		.join(pii)
		.on(pi.name == pii.parent)
		.left_join(item)
		.on(pii.item_code == item.name)
		.left_join(pip)
		.on(pi.name == pip.parent)
		.select(
			pi.name.as_("invoice"),
			pii.name,
			pii.parent,
			pi.posting_date,
			pi.debit_to,
			pi.customer,
			pi.remarks,
			fn.IfNull(pi.territory, "Not Specified").as_("territory"),
			pi.company,
			pi.base_net_total,
			pii.project,
			pii.item_code,
			pii.description,
			pii.item_name,
			pii.item_group,
			pii.item_name.as_("pi_item_name"),
			pii.item_group.as_("pi_item_group"),
			item.item_name.as_("i_item_name"),
			item.item_group.as_("i_item_group"),
			pii.sales_order,
			pii.delivery_note,
			pii.income_account,
			pii.cost_center,
			pii.enable_deferred_revenue,
			pii.deferred_revenue_account,
			pii.stock_qty,
			pii.stock_uom,
			pii.base_net_rate.as_("rate"),
			pii.base_net_amount.as_("amount"),
			pi.customer_name,
			fn.IfNull(pi.customer_group, "Not Specified").as_("customer_group"),
			pii.so_detail,
			pi.update_stock,
			pii.uom,
			pii.qty,
			fn.GROUP_CONCAT(pip.mode_of_payment).as_("mode_of_payment")

		)
		.where(pi.docstatus == 1)
		.where(pii.parenttype == doctype)
		.groupby(
			pi.name,
			pii.name,
			pii.parent,
			pi.posting_date,
			pi.debit_to,
			pi.customer,
			pi.remarks,
			pi.territory,
			pi.company,
			pi.base_net_total,
			pii.project,
			pii.item_code,
			pii.description,
			pii.item_name,
			pii.item_group,
			item.item_name,
			item.item_group,
			pii.sales_order,
			pii.delivery_note,
			pii.income_account,
			pii.cost_center,
			pii.enable_deferred_revenue,
			pii.deferred_revenue_account,
			pii.stock_qty,
			pii.stock_uom,
			pii.base_net_rate,
			pii.base_net_amount,
			pi.customer_name,
			pi.customer_group,
			pii.so_detail,
			pi.update_stock,
			pii.uom,
			pii.qty
		)
	)

	if additional_query_columns:
		for column in additional_query_columns:
			if column.get("_doctype"):
				table = frappe.qb.DocType(column.get("_doctype"))
				query = query.select(table[column.get("fieldname")])
			else:
				query = query.select(pi[column.get("fieldname")])

	if filters.get("customer"):
		query = query.where(pi.customer == filters["customer"])

	if filters.get("customer_group"):
		query = query.where(pi.customer_group == filters["customer_group"])

	query = apply_conditions(query, pi, pii, pip, filters, additional_conditions)

	from frappe.desk.reportview import build_match_conditions

	query, params = query.walk()
	match_conditions = build_match_conditions(doctype)

	if match_conditions:
		query += " and " + match_conditions

	query = apply_order_by_conditions(doctype, query, filters)

	return frappe.db.sql(query, params, as_dict=True)

