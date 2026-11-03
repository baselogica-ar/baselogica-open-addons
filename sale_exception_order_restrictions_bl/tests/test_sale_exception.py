# Copyright 2026 Base Lógica (baselogica.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, TransactionCase, new_test_user, tagged

RULES = (
    "exception_rule_payment_term",
    "exception_rule_missing_delivery_method",
    "exception_rule_delivery_method",
    "exception_rule_purchase_order",
    "exception_rule_urgent",
)
# the expired quotation: a rule with a filter on the native "Expired" field
EXPIRED = "exception_rule_expired_quotation"


@tagged("post_install", "-at_install")
class TestSaleException(TransactionCase):
    """Each restriction is an exception rule: it stops the salesperson and the
    administrator; the Sales administrator ignores the exceptions and confirms, with
    the differences in the note; an archived rule does not stop and a blocking one
    cannot be ignored; the portal and automated processes are not stopped."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.salesman = new_test_user(
            cls.env, "salesman_of_the_rules", groups="sales_team.group_sale_salesman"
        )
        cls.manager = new_test_user(
            cls.env, "manager_of_the_rules", groups="sales_team.group_sale_manager"
        )
        cls.portal = new_test_user(
            cls.env, "portal_of_the_rules", groups="base.group_portal"
        )
        cls.immediate = cls.env.ref("account.account_payment_term_immediate")
        cls.thirty_days = cls.env.ref("account.account_payment_term_30days")
        shipping = cls.env["product.product"].create(
            {"name": "Shipping of the rules", "type": "service"}
        )
        cls.zone, cls.other_zone = cls.env["delivery.carrier"].create(
            [
                {
                    "name": name,
                    "delivery_type": "fixed",
                    "fixed_price": 0.0,
                    "product_id": shipping.id,
                }
                for name in ("East Zone", "West Zone")
            ]
        )
        cls.customer = cls.env["res.partner"].create(
            {
                "name": "Store of the rules",
                "is_company": True,
                "property_payment_term_id": cls.thirty_days.id,
                "property_delivery_carrier_id": cls.zone.id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Detergent", "type": "consu", "list_price": 50.0}
        )
        cls.rules = {
            xmlid: cls.env.ref(f"sale_exception_order_restrictions_bl.{xmlid}")
            for xmlid in (*RULES, EXPIRED)
        }

    def _order(self, carrier=None, term=None, ref=False, urgent=False, expired=False):
        """The quotation through the form, as the salesperson enters it."""
        form = Form(self.env["sale.order"].with_user(self.salesman))
        form.partner_id = self.customer
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
        if expired:
            order.validity_date = fields.Date.context_today(order) - timedelta(days=1)
        return order

    def _exceptions(self, order, user=None):
        """The rules that stop the order, as the engine measures them at
        confirmation, without storing them."""
        self.env.invalidate_all()
        rule_ids = order.with_user(user or self.salesman)._get_exceptions()[0]
        return self.env["exception.rule"].browse(rule_ids)

    def _detect(self, order, user):
        """The exceptions stored on the order, as at confirmation, without rolling
        back the test transaction."""
        self.env.invalidate_all()
        order.with_user(user).with_context(
            base_exception_no_rollback={"sale.order": order.ids}
        ).detect_exceptions()

    def test_the_rules_come_active_and_not_blocking(self):
        """The five rules by method and the expired quotation one, with a filter: on
        the sales order, active and not blocking."""
        for xmlid, rule in self.rules.items():
            self.assertEqual(
                (rule.model, rule.exception_type, rule.active, rule.is_blocking),
                (
                    "sale.order",
                    "by_domain" if xmlid == EXPIRED else "by_method",
                    True,
                    False,
                ),
            )

    def test_each_brake_is_its_rule(self):
        """Each difference stops the order through its rule; an order like the form,
        through none."""
        self.customer.bl_purchase_order_required = True
        cases = (
            (self._order(carrier=self.zone, ref="OC 1"), []),
            (
                self._order(carrier=self.zone, term=self.immediate, ref="OC 2"),
                ["exception_rule_payment_term"],
            ),
            (self._order(ref="OC 3"), ["exception_rule_missing_delivery_method"]),
            (
                self._order(carrier=self.other_zone, ref="OC 4"),
                ["exception_rule_delivery_method"],
            ),
            (self._order(carrier=self.zone), ["exception_rule_purchase_order"]),
            (
                self._order(carrier=self.zone, ref="OC 5", urgent=True),
                ["exception_rule_urgent"],
            ),
            (self._order(carrier=self.zone, ref="OC 6", expired=True), [EXPIRED]),
        )
        for order, expected in cases:
            with self.subTest(order=order.name):
                self.assertEqual(
                    self._exceptions(order),
                    self.env["exception.rule"].union(
                        *(self.rules[xmlid] for xmlid in expected)
                    ),
                )

    def test_salesman_and_manager_are_braked(self):
        """An order with other terms is not confirmed, neither by the salesperson nor
        by the administrator without ignoring."""
        order = self._order(carrier=self.zone, term=self.immediate)
        for user in (self.salesman, self.manager):
            with self.assertRaises(UserError):
                order.with_user(user).action_confirm()
            self.assertEqual(order.state, "draft")

    def test_manager_ignores_and_confirms_with_the_note(self):
        """The Sales administrator ignores the exceptions and confirms: what differed
        stays in the note."""
        self.assertTrue(
            self.manager.has_group("base_exception.group_exception_rule_manager")
        )
        self.assertFalse(
            self.salesman.has_group("base_exception.group_exception_rule_manager")
        )
        order = self._order(carrier=self.zone, term=self.immediate)
        self._detect(order, self.salesman)
        self.assertEqual(order.exception_ids, self.rules["exception_rule_payment_term"])
        order.with_user(self.manager).action_ignore_exceptions()
        order.with_user(self.manager).action_confirm()
        self.assertEqual(order.state, "sale")
        note = order.message_ids.filtered(
            lambda m: "Confirmed with differences" in (m.body or "")
        )
        self.assertIn(self.immediate.display_name, note.body)
        self.assertEqual(note.author_id, self.manager.partner_id)
        self.assertFalse(order.activity_ids)

    def test_archived_rule_does_not_brake(self):
        """An archived rule does not stop: the order with other terms is confirmed,
        without a note."""
        self.rules["exception_rule_payment_term"].active = False
        order = self._order(carrier=self.zone, term=self.immediate)
        self.assertFalse(self._exceptions(order))
        order.with_user(self.salesman).action_confirm()
        self.assertEqual(order.state, "sale")

    def test_blocking_rule_cannot_be_ignored(self):
        """Nobody ignores a blocking rule, not even the Sales administrator."""
        self.rules["exception_rule_payment_term"].is_blocking = True
        order = self._order(carrier=self.zone, term=self.immediate)
        self._detect(order, self.manager)
        with self.assertRaises(UserError):
            order.with_user(self.manager).action_ignore_exceptions()

    def test_quantity_with_decimals(self):
        """Goods counted in units with decimals stop the order through a blocking rule
        that nobody ignores, not even the Sales administrator; whole units, goods in
        kilograms and a service with decimals do not stop it; half a dozen does."""
        rule = self.env.ref(
            "sale_exception_order_restrictions_bl.exception_rule_fractional_quantity"
        )
        self.assertTrue(rule.active and rule.is_blocking)
        order = self._order(carrier=self.zone)
        line = order.order_line.filtered(lambda line: line.product_id == self.product)
        line.product_uom_qty = 1.5
        self.assertEqual(self._exceptions(order), rule)
        self._detect(order, self.manager)
        with self.assertRaises(UserError):
            order.with_user(self.manager).action_ignore_exceptions()
        line.product_uom_qty = 2
        self.assertFalse(self._exceptions(order))
        flour = self.env["product.product"].create(
            {
                "name": "Flour",
                "type": "consu",
                "uom_id": self.env.ref("uom.product_uom_kgm").id,
            }
        )
        installation = self.env["product.product"].create(
            {"name": "Installation", "type": "service"}
        )
        order.order_line = [
            Command.create({"product_id": flour.id, "product_uom_qty": 1.5}),
            Command.create({"product_id": installation.id, "product_uom_qty": 0.5}),
        ]
        self.assertFalse(self._exceptions(order))
        line.write(
            {
                "product_uom_id": self.env.ref("uom.product_uom_dozen").id,
                "product_uom_qty": 0.5,
            }
        )
        self.assertEqual(self._exceptions(order), rule)

    def test_portal_is_not_braked(self):
        """The customer from the portal (with sudo) is not stopped: it confirms with
        the note and an activity for the salesperson."""
        order = self._order(carrier=self.other_zone)
        order.with_user(self.portal).sudo()._validate_order()
        self.assertEqual(order.state, "sale")
        self.assertFalse(order.exception_ids)
        self.assertEqual(order.activity_ids.user_id, self.salesman)

    def test_filter_rule_of_the_customer(self):
        """A rule with a filter, like the ones each company creates: it stops the
        salesperson; the portal confirms anyway, with its name in the note and an
        activity for the salesperson."""
        rule = self.env["exception.rule"].create(
            {
                "name": "Test rule with a filter",
                "model": "sale.order",
                "exception_type": "by_domain",
                "domain": "[('client_order_ref', '=', 'WITH FILTER')]",
            }
        )
        order = self._order(carrier=self.zone, ref="WITH FILTER")
        self.assertEqual(self._exceptions(order), rule)
        with self.assertRaises(UserError):
            order.with_user(self.salesman).action_confirm()
        order.with_user(self.portal).sudo()._validate_order()
        self.assertEqual(order.state, "sale")
        note = order.message_ids.filtered(
            lambda m: "Confirmed with differences" in (m.body or "")
        )
        self.assertIn("Test rule with a filter", note.body)
        self.assertEqual(order.activity_ids.user_id, self.salesman)

    def test_expired_quotation(self):
        """The expired quotation stops the salesperson; the one expiring today does
        not. The Sales administrator ignores the exceptions and confirms it with its
        prices, and the note says so."""
        order = self._order(carrier=self.zone)
        today = fields.Date.context_today(order)
        order.validity_date = today
        self.assertFalse(self._exceptions(order))
        order.validity_date = today - timedelta(days=1)
        self.assertEqual(self._exceptions(order), self.rules[EXPIRED])
        with self.assertRaises(UserError):
            order.with_user(self.salesman).action_confirm()
        self.assertEqual(order.state, "draft")
        self._detect(order, self.salesman)
        order.with_user(self.manager).action_ignore_exceptions()
        order.with_user(self.manager).action_confirm()
        self.assertEqual(order.state, "sale")
        note = order.message_ids.filtered(
            lambda m: "Confirmed with differences" in (m.body or "")
        )
        self.assertIn(self.rules[EXPIRED].name, note.body)

    def test_update_prices_of_an_expired_quotation(self):
        """ "Update Prices" on the expired quotation: today's prices, today's date, a
        new expiration and the total before and after in the history; with that, the
        rule no longer stops it."""
        order = self._order(carrier=self.zone, expired=True)
        self.assertEqual(self._exceptions(order), self.rules[EXPIRED])
        self.product.list_price = 60.0
        order.with_user(self.salesman).action_bl_update_prices()
        line = order.order_line.filtered(lambda line: line.product_id == self.product)
        self.assertEqual(line.price_unit, 60.0)
        self.assertFalse(order.is_expired)
        self.assertEqual(order.date_order.date(), fields.Date.context_today(order))
        self.assertTrue(
            order.message_ids.filtered(
                lambda m: "Prices updated to today" in (m.body or "")
            )
        )
        self.assertFalse(self._exceptions(order))

    def test_update_prices_only_when_expired(self):
        """While the quotation is valid, its prices hold: it is not updated."""
        order = self._order(carrier=self.zone)
        with self.assertRaises(UserError):
            order.with_user(self.salesman).action_bl_update_prices()

    def test_only_a_sales_administrator_ignores_or_unlocks(self):
        """Ignoring the restrictions and unlocking a confirmed order belong to the
        Sales administrator, also through the API: the salesperson can neither call
        the button nor set the field; the administrator can."""
        order = self._order(carrier=self.zone, expired=True)
        with self.assertRaises(AccessError):
            order.with_user(self.salesman).action_ignore_exceptions()
        with self.assertRaises(AccessError):
            order.with_user(self.salesman).write({"ignore_exception": True})
        self.assertFalse(order.ignore_exception)
        order.with_user(self.manager).action_ignore_exceptions()
        order.with_user(self.manager).action_confirm()
        order.with_user(self.manager).action_lock()
        self.assertTrue(order.locked)
        with self.assertRaises(AccessError):
            order.with_user(self.salesman).action_unlock()
        with self.assertRaises(AccessError):
            order.with_user(self.salesman).write({"locked": False})
        self.assertTrue(order.locked)
        order.with_user(self.manager).action_unlock()
        self.assertFalse(order.locked)

    def test_duplicate_keeps_the_quoted_prices(self):
        """Duplicating an expired quotation does not reprice it: Odoo copies the
        prices and only renews the expiration. That is why the rule asks for "Update
        Prices"; if a version changes this, the text of the rule changes."""
        order = self._order(carrier=self.zone, expired=True)
        self.product.list_price = 60.0
        copy = order.copy()
        self.assertFalse(copy.is_expired)
        self.assertEqual(
            copy.order_line.filtered(
                lambda line: line.product_id == self.product
            ).price_unit,
            50.0,
        )
        new = self._order(carrier=self.zone)
        self.assertEqual(
            new.order_line.filtered(
                lambda line: line.product_id == self.product
            ).price_unit,
            60.0,
        )
