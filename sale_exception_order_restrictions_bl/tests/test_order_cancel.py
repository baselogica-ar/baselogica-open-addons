# Copyright 2026 Base Lógica (baselogica.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.sale.tests.common import TestSaleCommon


@tagged("post_install", "-at_install")
class TestOrderCancel(TestSaleCommon):
    """An order with quantities invoiced is not cancelled, neither from the order nor
    from "Cancel" of the list, which skips the lock of confirmed orders: Odoo would
    leave the invoice valid and the order cancelled. It is undone with the credit
    note, and then it is cancelled. A draft invoice does not stop it: Odoo cancels it
    with the order. The quantities delivered, in test_sale_order_restrictions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # a service invoiced as ordered, without taxes: no rule of the module looks
        # at it
        cls.service = cls.env["product.product"].create(
            {
                "name": "Installation of the cancel",
                "type": "service",
                "list_price": 100.0,
                "invoice_policy": "order",
                "taxes_id": False,
            }
        )

    def _confirmed_order(self):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [Command.create({"product_id": self.service.id})],
            }
        )
        order.action_confirm()
        self.assertEqual(order.state, "sale")
        self.assertTrue(order.locked)
        return order

    def _mass_cancel(self, order):
        """ "Cancel" from the list: the native wizard, which cancels without the
        lock check of the order's button."""
        return (
            self.env["sale.mass.cancel.orders"]
            .create({"sale_order_ids": [Command.set(order.ids)]})
            .action_mass_cancel()
        )

    def test_invoiced_order_is_cancelled_after_its_credit_note(self):
        """With its invoice posted, the order is not cancelled from the list, nor
        from the order once a Sales administrator unlocks it; with the credit note
        of the whole invoice, nothing is left invoiced and it is cancelled."""
        order = self._confirmed_order()
        invoice = order._create_invoices()
        invoice.action_post()
        with self.assertRaisesRegex(UserError, "delivered or invoiced"):
            self._mass_cancel(order)
        order.action_unlock()
        with self.assertRaisesRegex(UserError, "delivered or invoiced"):
            order.action_cancel()
        self.assertEqual(order.state, "sale")
        self.env["account.move.reversal"].with_context(
            active_model="account.move", active_ids=invoice.ids
        ).create({"journal_id": invoice.journal_id.id}).refund_moves()
        refund = order.invoice_ids.filtered(lambda move: move.move_type == "out_refund")
        self.assertTrue(refund)
        refund.filtered(lambda move: move.state == "draft").action_post()
        order.action_cancel()
        self.assertEqual(order.state, "cancel")
        self.assertEqual(invoice.state, "posted")

    def test_draft_invoice_is_cancelled_with_the_order(self):
        """A draft invoice was not sent to anyone: the order is cancelled, also from
        the list, and Odoo cancels the invoice with it."""
        order = self._confirmed_order()
        invoice = order._create_invoices()
        self._mass_cancel(order)
        self.assertEqual(order.state, "cancel")
        self.assertEqual(invoice.state, "cancel")

    def test_invoiced_down_payment_stops_the_cancel(self):
        """A down payment invoiced also stops it, although its line on the order has
        no unit."""
        order = self._confirmed_order()
        self.env["sale.advance.payment.inv"].with_context(
            active_model="sale.order", active_ids=order.ids
        ).create(
            {"advance_payment_method": "percentage", "amount": 10}
        ).create_invoices()
        order.invoice_ids.action_post()
        down_payment = order.order_line.filtered(
            lambda line: line.is_downpayment and not line.display_type
        )
        self.assertTrue(down_payment)
        self.assertFalse(down_payment.product_uom_id)
        with self.assertRaisesRegex(UserError, "delivered or invoiced"):
            self._mass_cancel(order)
        self.assertEqual(order.state, "sale")
