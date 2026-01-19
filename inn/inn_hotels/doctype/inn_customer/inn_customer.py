# Copyright (c) 2024, Core Initiative and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class InnCustomer(Document):
    pass

    def before_insert(self, *args, **kwargs):

        doc_supp_group = frappe.db.get_single_value(
            doctype="Inn Hotels Setting", fieldname="inn_customer_group_as_supplier"
        )
        if doc_supp_group is None:
            doc_supp_group = ""

        doc_sup = frappe.new_doc("Supplier")
        doc_sup.supplier_name = self.customer_name
        doc_sup.supplier_type = self.customer_type
        doc_sup.supplier_group = doc_supp_group

        try:
            doc_sup.save()
            self.supplier_name = doc_sup.name
        except Exception as e:
            frappe.log_error(
                "Error creating supplier for Inn Customer:", message=str(e)
            )
            frappe.throw("Failed to create associated supplier record")

    def after_delete(self, *args, **kwargs):
        frappe.db.delete("Customer", {"customer_name": self.customer_name})
        frappe.db.delete("Supplier", {"supplier_name": self.customer_name})


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def filter_customer_supplier(doctype, txt, searchfield, start, page_len, filters):
    """
    Filter customers, excluding those that are linked to suppliers via Inn Customer doctype.
    Optimized for performance using SQL joins.
    """
    # Build the base query conditions
    conditions = []
    values = []

    # Add search text filter if provided
    if txt:
        field_name = searchfield or "name"
        conditions.append(f"c.{field_name} LIKE %s")
        values.append(f"%{txt}%")

    # Add additional filters if provided
    if filters:
        for key, value in filters.items():
            if isinstance(value, list):
                conditions.append(f"c.{key} {value[0]} %s")
                values.append(value[1])
            else:
                conditions.append(f"c.{key} = %s")
                values.append(value)

    # Build WHERE clause
    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Use SQL query with LEFT JOIN to exclude customers that are linked to suppliers via Inn Customer
    # This is the most accurate and efficient approach using the proper relationship table
    query = f"""
        SELECT c.name, c.customer_name
        FROM `tabCustomer` c
        LEFT JOIN `tabInn Customer` ic ON c.name = ic.customer_name
        WHERE {where_clause}
        AND ic.name IS NULL
        ORDER BY c.modified DESC
        LIMIT %s OFFSET %s
    """

    # Add pagination parameters
    values.extend([page_len, start])

    # Execute the query
    result = frappe.db.sql(query, values, as_dict=True)

    # Return in the expected format
    return [(row.name, row.customer_name) for row in result]
