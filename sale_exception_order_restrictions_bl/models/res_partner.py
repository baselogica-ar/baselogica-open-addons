# Copyright 2026 Base Lógica (baselogica.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    bl_purchase_order_required = fields.Boolean(
        string="Purchase Order Required",
        help="The order is not confirmed without the Customer Reference: the number of "
        "the customer's purchase order.",
        tracking=True,
    )

    def _commercial_fields(self):
        # set on the company, followed by its branches and addresses
        res = super()._commercial_fields()
        return res + ["bl_purchase_order_required"]
