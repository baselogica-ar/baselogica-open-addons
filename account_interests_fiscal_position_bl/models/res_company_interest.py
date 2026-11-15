# Copyright 2026 Base Lógica (baselogica.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from collections import defaultdict

from odoo import Command, models
from odoo.tools import safe_eval


class ResCompanyInterest(models.Model):
    _inherit = "res.company.interest"

    def _prepare_interest_invoice(self, partner, debt, to_date, journal):
        vals = super()._prepare_interest_invoice(partner, debt, to_date, journal)
        if not vals:
            return vals
        position = self._bl_overdue_fiscal_position(partner, to_date)
        if position is None:
            # nothing to read: the one of the customer's form, as the interests module
            position = self.env["account.fiscal.position"].browse(
                vals["fiscal_position_id"]
            )
        # the taxes of the product as Odoo picks them on an invoice line: the ones of
        # the company or, for a branch without its own, of its parent company
        taxes = position.map_tax(
            self.interest_product_id.taxes_id._filter_taxes_by_company(self.company_id)
        )
        vals["fiscal_position_id"] = position.id
        for command in vals["invoice_line_ids"]:
            command[2]["tax_ids"] = [Command.set(taxes.ids)]
        return vals

    def _bl_overdue_fiscal_position(self, partner, to_date):
        """The fiscal position of the invoices whose interest the note charges: the ones
        still overdue at the end of the period and, with late payment interest, the ones
        paid late in it, with the same filters as the interests module. With several,
        the one of the largest part of the debt; None when there is no invoice."""
        self.ensure_one()
        debt = defaultdict(float)
        overdue = self.env["account.move.line"].search(
            self._get_move_line_domains()
            + [
                ("partner_id", "=", partner.id),
                ("amount_residual", ">", 0),
                ("date_maturity", "<", to_date),
            ]
        )
        for line in overdue:
            debt[line.move_id.fiscal_position_id] += line.amount_residual
        if self.late_payment_interest:
            from_date = to_date + self._calculate_date_deltas(
                self.rule_type, -self.interval
            )
            domain = [
                ("debit_move_id.partner_id", "=", partner.id),
                ("debit_move_id.parent_state", "=", "posted"),
                ("debit_move_id.account_id", "in", self.receivable_account_ids.ids),
                ("credit_move_id.date", ">=", from_date),
                ("credit_move_id.date", "<", to_date),
            ]
            if self.domain:
                domain.append(
                    (
                        "debit_move_id",
                        "any",
                        safe_eval.safe_eval(self.domain, self._get_eval_context()),
                    )
                )
            for part in self.env["account.partial.reconcile"].search(domain):
                paid = part.debit_move_id
                if paid.date_maturity and part.credit_move_id.date > paid.date_maturity:
                    debt[paid.move_id.fiscal_position_id] += part.amount
        if not debt:
            return None
        return max(debt, key=debt.get)
