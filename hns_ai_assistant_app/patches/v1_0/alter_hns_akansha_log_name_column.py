import frappe


def execute():
	try:
		if frappe.db.table_exists("Hns Akansha Log"):
			column_type = frappe.db.get_column_type("Hns Akansha Log", "name")
			if "varchar" not in str(column_type).lower():
				frappe.db.sql("ALTER TABLE `tabHns Akansha Log` MODIFY `name` varchar(140) NOT NULL")
		frappe.db.delete("Property Setter", {"doc_type": "Hns Akansha Log", "field_name": "naming_series"})
	except Exception as e:
		frappe.log_error(title="Alter Hns Akansha Log Name Column Patch Error", message=str(e))
		raise

