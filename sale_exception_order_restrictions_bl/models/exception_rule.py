# Copyright 2026 Base Lógica (baselogica.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models

METHODS = [
    ("_bl_exception_payment_term", "Payment terms other than the customer's"),
    (
        "_bl_exception_missing_delivery_method",
        "Order with goods and no delivery method",
    ),
    ("_bl_exception_delivery_method", "Delivery method other than the customer's"),
    ("_bl_exception_purchase_order", "Customer's purchase order missing"),
    ("_bl_exception_urgent", "Urgent order"),
]


class ExceptionRule(models.Model):
    _inherit = "exception.rule"

    method = fields.Selection(
        selection_add=METHODS,
        ondelete={method: "cascade" for method, _label in METHODS},
    )
