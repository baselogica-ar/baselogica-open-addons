# Copyright 2026 Base Lógica (baselogica.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Sale Exception Order Restrictions",
    "summary": "Sales orders that follow the customer's form: exception rules, locked "
    "confirmed orders and no cancelling of what was delivered or invoiced.",
    "version": "20.0.1.4.1",
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
