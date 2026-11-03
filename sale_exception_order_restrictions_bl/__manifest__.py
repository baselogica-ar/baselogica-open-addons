# Copyright 2026 Base Lógica (baselogica.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Sale Exception Order Restrictions",
    "summary": "The sales order is not confirmed apart from the customer's form, "
    "without the purchase order the customer requires, urgent or with its quotation "
    'expired ("Update Prices" brings today\'s prices): exception rules that a Sales '
    "administrator ignores; never with a quantity with decimals of goods counted in "
    "units; confirmed orders are locked, and an order with goods delivered or invoiced "
    "is not cancelled.",
    "version": "20.0.1.1.0",
    "category": "Sales/Sales",
    "author": "Base Lógica",
    "website": "https://github.com/baselogica-ar/baselogica-open-addons",
    "license": "AGPL-3",
    "development_status": "Beta",
    "depends": ["delivery", "sale_exception"],
    "data": [
        "security/res_groups_data.xml",
        "data/crm_tag_data.xml",
        "data/exception_rule_data.xml",
        "data/ir_filters_data.xml",
        "views/delivery_carrier_views.xml",
        "views/res_partner_views.xml",
        "views/sale_order_views.xml",
    ],
    "post_init_hook": "post_init_hook",
}
