# Copyright 2026 Base Lógica (baselogica.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo.tests import Form, TransactionCase, new_test_user, tagged

RULE = "sale_exception_order_restrictions_bl.exception_rule_credit_limit"


@tagged("post_install", "-at_install")
class TestCreditLimitRule(TransactionCase):
    """The credit limit rule comes archived: the company that wants it activates it,
    with Odoo's customer credit limit turned on in Accounting. Active, it stops the
    order that takes the customer over its limit, with the same amount Odoo warns
    about on the quotation (what the customer owes, its confirmed orders to invoice
    and this order); a Sales administrator ignores it. Archived, it leaves nothing:
    neither a stop nor a note."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.salesman = new_test_user(
            cls.env, "salesman_of_the_credit", groups="sales_team.group_sale_salesman"
        )
        cls.manager = new_test_user(
            cls.env, "manager_of_the_credit", groups="sales_team.group_sale_manager"
        )
        cls.portal = new_test_user(
            cls.env, "portal_of_the_credit", groups="base.group_portal"
        )
        cls.rule = cls.env.ref(RULE)
        cls.env.company.account_use_credit_limit = True
        cls.customer = cls.env["res.partner"].create(
            {"name": "Store of the credit", "is_company": True}
        )
        cls.customer.credit_limit = 100.0
        # a service without taxes: no other rule of the module looks at it, and the
        # amounts are the ones of the test
        cls.product = cls.env["product.product"].create(
            {
                "name": "Consulting of the credit",
                "type": "service",
                "list_price": 50.0,
                "taxes_id": False,
            }
        )

    def _order(self, quantity):
        """The quotation through the form, as the salesperson enters it."""
        form = Form(self.env["sale.order"].with_user(self.salesman))
        form.partner_id = self.customer
        with form.order_line.new() as line:
            line.product_id = self.product
            line.product_uom_qty = quantity
        return form.save()

    def _exceptions(self, order, user=None):
        """The rules that stop the order, as the engine measures them at
        confirmation, without storing them."""
        self.env.invalidate_all()
        rule_ids = order.with_user(user or self.salesman)._get_exceptions()[0]
        return self.env["exception.rule"].browse(rule_ids)

    def _note(self, order):
        return order.message_ids.filtered(
            lambda m: "Confirmed with differences" in (m.body or "")
        )

    def test_the_rule_comes_archived(self):
        """By method, not blocking and archived: no base stops an order for credit
        until its company activates the rule."""
        self.assertEqual(
            (
                self.rule.model,
                self.rule.exception_type,
                self.rule.method,
                self.rule.active,
                self.rule.is_blocking,
            ),
            ("sale.order", "by_method", "_bl_exception_credit_limit", False, False),
        )

    def test_archived_it_does_not_stop_nor_leave_a_note(self):
        """Archived, the order over the limit is confirmed by the salesperson, and
        the portal confirms it without a note or an activity: Odoo's warning on the
        quotation is the only sign."""
        order = self._order(3)
        self.assertTrue(order.partner_credit_warning)
        self.assertFalse(self._exceptions(order))
        order.with_user(self.salesman).action_confirm()
        self.assertEqual(order.state, "sale")
        portal_order = self._order(3)
        portal_order.with_user(self.portal).sudo()._validate_order()
        self.assertEqual(portal_order.state, "sale")
        self.assertFalse(self._note(portal_order))
        self.assertFalse(portal_order.activity_ids)

    def test_active_it_stops_the_order_over_the_limit(self):
        """Active, the order that takes the customer over its limit stops (150 over
        100) and the one within the limit does not (50); the Sales administrator
        ignores it and confirms, with Odoo's warning in the note."""
        self.rule.active = True
        order = self._order(3)
        self.assertEqual(self._exceptions(order), self.rule)
        self.assertFalse(self._exceptions(self._order(1)))
        self.env.invalidate_all()
        order.with_user(self.salesman).with_context(
            base_exception_no_rollback={"sale.order": order.ids}
        ).detect_exceptions()
        self.assertEqual(order.exception_ids, self.rule)
        order.with_user(self.manager).action_ignore_exceptions()
        order.with_user(self.manager).action_confirm()
        self.assertEqual(order.state, "sale")
        self.assertIn("credit limit", self._note(order).body)

    def test_what_the_customer_already_has_counts(self):
        """The confirmed orders to invoice count, as in Odoo's warning: after a first
        order of 60, a second one of 50 takes the customer to 110, over its limit
        of 100."""
        self.rule.active = True
        first = self._order(1.2)
        self.assertFalse(self._exceptions(first))
        first.with_user(self.salesman).action_confirm()
        self.assertEqual(first.state, "sale")
        self.assertEqual(self._exceptions(self._order(1)), self.rule)

    def test_without_the_credit_limit_of_accounting(self):
        """Without the customer credit limit turned on in Accounting, the active
        rule does not stop: Odoo does not compute the warning."""
        self.rule.active = True
        self.env.company.account_use_credit_limit = False
        self.assertFalse(self._exceptions(self._order(3)))

    def test_the_portal_over_the_limit_leaves_the_note(self):
        """Active, the portal is not stopped either: the order over the limit is
        confirmed with Odoo's warning in the note and an activity for the
        salesperson."""
        self.rule.active = True
        order = self._order(3)
        order.with_user(self.portal).sudo()._validate_order()
        self.assertEqual(order.state, "sale")
        self.assertIn("credit limit", self._note(order).body)
        self.assertEqual(order.activity_ids.user_id, self.salesman)
