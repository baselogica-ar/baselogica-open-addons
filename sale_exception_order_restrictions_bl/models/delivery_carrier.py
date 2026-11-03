# Copyright 2026 Base Lógica (baselogica.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    # A module that creates its own pickup methods may declare the same field and set it
    # on them without depending on this one: Odoo keeps a single column for both
    # declarations.
    bl_customer_collects = fields.Boolean(
        string="Customer Collects",
        help="The customer collects the goods (a pickup): an order may use this method "
        "although its delivery address "
        "has another one.",
    )
