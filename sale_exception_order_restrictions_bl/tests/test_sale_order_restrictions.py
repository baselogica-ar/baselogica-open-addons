# Copyright 2026 Base Lógica (baselogica.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import Command
from odoo.tests import Form, TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestSaleOrderRestrictions(TransactionCase):
    """What each restriction checks at confirmation: the order that departs from the
    customer's form, the one without the purchase order the customer requires and the
    urgent one. The exception engine stops it (its tests, in test_sale_exception);
    here, each difference with its values, and the portal and automated processes,
    which confirm with the note and an activity for the salesperson."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.salesman = new_test_user(
            cls.env,
            "salesman_of_the_restrictions",
            groups="sales_team.group_sale_salesman",
        )
        cls.portal = new_test_user(
            cls.env, "portal_of_the_restrictions", groups="base.group_portal"
        )
        cls.immediate = cls.env.ref("account.account_payment_term_immediate")
        cls.thirty_days = cls.env.ref("account.account_payment_term_30days")
        shipping = cls.env["product.product"].create(
            {"name": "Test shipping", "type": "service"}
        )
        cls.zone = cls.env["delivery.carrier"].create(
            {
                "name": "North Zone",
                "delivery_type": "fixed",
                "fixed_price": 0.0,
                "product_id": shipping.id,
            }
        )
        cls.other_zone = cls.env["delivery.carrier"].create(
            {
                "name": "South Zone",
                "delivery_type": "fixed",
                "fixed_price": 0.0,
                "product_id": shipping.id,
            }
        )
        cls.customer = cls.env["res.partner"].create(
            {
                "name": "Test store",
                "is_company": True,
                "property_payment_term_id": cls.thirty_days.id,
                "property_delivery_carrier_id": cls.zone.id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Bleach", "type": "consu", "list_price": 100.0}
        )

    def _order(
        self, user=None, partner=None, carrier=None, term=None, ref=False, urgent=False
    ):
        """The quotation through the form, as the salesperson enters it; the method,
        with the shipping of the order."""
        form = Form(self.env["sale.order"].with_user(user or self.salesman))
        form.partner_id = partner or self.customer
        if term:
            form.payment_term_id = term
        if ref:
            form.client_order_ref = ref
        with form.order_line.new() as line:
            line.product_id = self.product
        order = form.save()
        if carrier:
            order.sudo().set_delivery_line(carrier, 0.0)
        if urgent:
            order.sudo().tag_ids = self.env.ref(
                "sale_exception_order_restrictions_bl.crm_tag_urgent"
            )
        return order

    def _confirm(self, order, user):
        self.env.invalidate_all()
        return order.with_user(user).action_confirm()

    def _differences(self, order):
        return order.with_user(self.salesman)._bl_confirmation_differences()

    def test_order_like_the_form_confirms(self):
        """The terms and the method of the form: no differences, it confirms without
        a note."""
        order = self._order(carrier=self.zone)
        self.assertFalse(self._differences(order))
        self._confirm(order, self.salesman)
        self.assertEqual(order.state, "sale")
        self.assertFalse(
            order.message_ids.filtered(lambda m: "differences" in (m.body or ""))
        )

    def test_other_payment_terms(self):
        """Other terms than the form's: the difference names both."""
        order = self._order(carrier=self.zone, term=self.immediate)
        (text,) = self._differences(order)
        self.assertIn(self.immediate.display_name, text)
        self.assertIn(self.thirty_days.display_name, text)
        self.assertTrue(order._bl_payment_term_difference())

    def test_other_delivery_method_or_none(self):
        """Another method than the form's is a difference, and so is an order with
        goods and no method."""
        order = self._order(carrier=self.other_zone)
        (text,) = self._differences(order)
        self.assertIn("South Zone", text)
        self.assertIn("North Zone", text)
        self.assertTrue(order._bl_delivery_method_difference())
        order = self._order()
        self.assertEqual(self._differences(order), ["no delivery method"])
        self.assertTrue(order._bl_missing_delivery_method())
        self.assertFalse(order._bl_delivery_method_difference())

    def test_form_without_terms_or_method_has_no_difference(self):
        """A form without terms or method has nothing to compare with."""
        bare = self.env["res.partner"].create(
            {"name": "Customer without form", "is_company": True}
        )
        order = self._order(partner=bare, carrier=self.other_zone, term=self.immediate)
        self.assertFalse(self._differences(order))
        self._confirm(order, self.salesman)
        self.assertEqual(order.state, "sale")

    def test_portal_confirms_with_note_and_activity(self):
        """The customer from the portal (the path of its controller, with sudo) is
        not stopped: the order is confirmed with the note and an activity for its
        salesperson."""
        order = self._order(carrier=self.other_zone)
        order.with_user(self.portal).sudo()._validate_order()
        self.assertEqual(order.state, "sale")
        note = order.message_ids.filtered(
            lambda m: "Confirmed with differences" in (m.body or "")
        )
        self.assertIn("South Zone", note.body)
        self.assertEqual(order.activity_ids.user_id, self.salesman)

    def test_pickups_have_no_difference(self):
        """A method where the customer collects the goods (a pickup) is valid for any
        delivery address."""
        pickup = self.zone.copy(
            {"name": "Counter pickup", "bl_customer_collects": True}
        )
        order = self._order(carrier=pickup)
        self.assertFalse(self._differences(order))
        self._confirm(order, self.salesman)
        self.assertEqual(order.state, "sale")

    def test_purchase_order_required(self):
        """The customer that requires its purchase order: without the Customer
        Reference, or with blanks, it is missing; with the number, it is not. A
        branch of the company that is set, too."""
        self.customer.bl_purchase_order_required = True
        branch = self.env["res.partner"].create(
            {"name": "Downtown branch", "parent_id": self.customer.id}
        )
        self.assertTrue(branch.bl_purchase_order_required)
        for partner, ref in (
            (self.customer, False),
            (self.customer, "   "),
            (branch, False),
        ):
            (text,) = self._differences(
                self._order(partner=partner, carrier=self.zone, ref=ref)
            )
            self.assertIn("purchase order", text)
        order = self._order(carrier=self.zone, ref="PO 4512")
        self.assertFalse(self._differences(order))
        self._confirm(order, self.salesman)
        self.assertEqual(order.state, "sale")

    def test_urgent_order(self):
        """The urgent order says so in its differences; the favorite filter of urgent
        orders finds it by its tag."""
        order = self._order(carrier=self.zone, urgent=True)
        self.assertTrue(order._bl_is_urgent())
        self.assertEqual(self._differences(order), ["the order is urgent"])
        favorite = self.env.ref(
            "sale_exception_order_restrictions_bl.filter_sale_order_urgent_to_confirm"
        )
        self.assertIn(
            str(self.env.ref("sale_exception_order_restrictions_bl.crm_tag_urgent").id),
            favorite.domain,
        )

    def test_confirmed_orders_are_locked_for_everyone(self):
        """The native lock of confirmed orders applies to everyone on install."""
        self.assertTrue(self.salesman.has_group("sale.group_auto_done_setting"))
        order = self._order(carrier=self.zone)
        self._confirm(order, self.salesman)
        self.assertTrue(order.locked)

    def test_quotation_lines_without_goods_need_no_method(self):
        """A quotation of services only asks for no delivery method."""
        service = self.env["product.product"].create(
            {"name": "Installation", "type": "service"}
        )
        bare = self.env["res.partner"].create(
            {"name": "Services customer", "is_company": True}
        )
        order = (
            self.env["sale.order"]
            .with_user(self.salesman)
            .create(
                {
                    "partner_id": bare.id,
                    "order_line": [Command.create({"product_id": service.id})],
                }
            )
        )
        self.assertFalse(self._differences(order))
        self._confirm(order, self.salesman)
        self.assertEqual(order.state, "sale")
