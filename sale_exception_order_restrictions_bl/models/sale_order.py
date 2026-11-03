# Copyright 2026 Base Lógica (baselogica.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from markupsafe import Markup

from odoo import fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date, formatLang


class SaleOrder(models.Model):
    """The restrictions of the order at confirmation, as rules of the community
    exception engine (``sale_exception``): Odoo does not stop an order that departs
    from the customer's form, that lacks the purchase order the customer requires or
    that is urgent, and it stops the expired quotation only in the portal. Each
    restriction is a rule "by method" (what it checks lives here, with its tests: an
    Odoo filter cannot compare the order with the customer's form), except the
    expired quotation, a rule with a filter on "Expired", the native field; each
    company archives a rule or makes it blocking, and creates its own rules with a
    filter. The portal and automated processes are not stopped by any rule: they
    confirm with a note and an activity for the salesperson."""

    _inherit = "sale.order"

    def _bl_payment_term_difference(self):
        """Payment terms other than the ones Odoo proposes: those of the customer's
        form, with the company of the order. A form without payment terms does not
        stop the order."""
        self.ensure_one()
        term = self.with_company(self.company_id).partner_id.property_payment_term_id
        if not term or self.payment_term_id == term:
            return False
        return self.env._(
            "payment terms %(order)s in the order and %(form)s in the form",
            order=self.payment_term_id.display_name or self.env._("none"),
            form=term.display_name,
        )

    def _bl_has_goods(self):
        return bool(
            self.order_line.filtered(
                lambda line: line.product_id.type == "consu" and not line.is_delivery
            )
        )

    def _bl_missing_delivery_method(self):
        """The order with goods and no delivery method."""
        self.ensure_one()
        return (
            self.env._("no delivery method")
            if self._bl_has_goods() and not self.carrier_id
            else False
        )

    def _bl_delivery_method_difference(self):
        """A delivery method other than the one "Add a shipping method" proposes: the
        one of the delivery address or of its company, with the company of the order.
        A method where the customer collects the goods (a pickup) and a form without
        a method do not stop the order."""
        self.ensure_one()
        shipping = self.with_company(self.company_id).partner_shipping_id
        carrier = shipping.property_delivery_carrier_id.filtered("active") or (
            shipping.commercial_partner_id.property_delivery_carrier_id.filtered(
                "active"
            )
        )
        if (
            not carrier
            or not self.carrier_id
            or self.carrier_id == carrier
            or self.carrier_id.bl_customer_collects
        ):
            return False
        return self.env._(
            "delivery method %(order)s in the order and %(form)s in the form",
            order=self.carrier_id.display_name,
            form=carrier.display_name,
        )

    def _bl_missing_purchase_order(self):
        """An empty Customer Reference when the customer requires its purchase order."""
        self.ensure_one()
        customer = self.partner_id.commercial_partner_id
        if (
            not customer.bl_purchase_order_required
            or (self.client_order_ref or "").strip()
        ):
            return False
        return self.env._(
            "no Customer Reference, and %(customer)s requires its purchase order",
            customer=customer.display_name,
        )

    def _bl_fractional_quantity(self):
        """A line of goods counted in units (the unit, or a unit that relates to it,
        like a dozen or a pack) with decimals, like 1.5 units: goods counted in units
        are sold whole, and Odoo lets the fraction reach the warehouse. Setting the
        precision of the quantities to whole numbers is not the same: it rounds
        without warning, also what the barcode scanner adds up."""
        self.ensure_one()
        unit = self.env.ref("uom.product_uom_unit")
        lines = self.order_line.filtered(
            lambda line: (
                not line.display_type
                and not line.is_delivery
                and line.product_id.type == "consu"
                and (line.product_uom_id.parent_path or "").startswith(f"{unit.id}/")
                and abs(line.product_uom_qty - round(line.product_uom_qty)) > 0.00001
            )
        )
        if not lines:
            return False
        return self.env._(
            "a quantity with decimals in %(products)s",
            products=", ".join(lines.product_id.mapped("display_name")),
        )

    def _bl_is_urgent(self):
        self.ensure_one()
        tag = self.env.ref(
            "sale_exception_order_restrictions_bl.crm_tag_urgent",
            raise_if_not_found=False,
        )
        return bool(tag) and tag in self.tag_ids

    def _bl_confirmation_differences(self):
        """What sets the order apart from the customer's form, what it lacks and the
        filter rules it matches, as texts of the note."""
        self.ensure_one()
        texts = (
            self._bl_payment_term_difference(),
            self._bl_missing_delivery_method(),
            self._bl_delivery_method_difference(),
            self._bl_missing_purchase_order(),
            self._bl_is_urgent() and self.env._("the order is urgent"),
            self._bl_fractional_quantity(),
        )
        rules = (
            self.env["exception.rule"]
            .sudo()
            .search(
                [("model", "=", "sale.order"), ("exception_type", "=", "by_domain")]
            )
        )
        # the filter rules each company creates, by their name
        filters = [
            rule.name for rule in rules if self.filtered_domain(rule._get_domain())
        ]
        return [text for text in texts if text] + filters

    def _bl_confirms_without_brakes(self):
        """The portal and automated processes (a system process) are not stopped: the
        order is confirmed with its note and an activity for its salesperson, who
        reviews the difference."""
        return self.env.user.share or self.env.is_superuser()

    def detect_exceptions(self):
        if self._bl_confirms_without_brakes():
            return []
        return super().detect_exceptions()

    def _bl_exception_payment_term(self):
        return self.filtered(lambda order: order._bl_payment_term_difference())

    def _bl_exception_missing_delivery_method(self):
        return self.filtered(lambda order: order._bl_missing_delivery_method())

    def _bl_exception_delivery_method(self):
        return self.filtered(lambda order: order._bl_delivery_method_difference())

    def _bl_exception_purchase_order(self):
        return self.filtered(lambda order: order._bl_missing_purchase_order())

    def _bl_exception_urgent(self):
        return self.filtered(lambda order: order._bl_is_urgent())

    def _bl_exception_fractional_quantity(self):
        return self.filtered(lambda order: order._bl_fractional_quantity())

    def _action_cancel(self):
        """An order with goods delivered or invoiced is not cancelled: Odoo cancels
        only what is pending and leaves the invoice and the delivered goods as they
        are, so the cancelled order would be wrong. It is undone with the return and
        the credit note from the order; with nothing delivered or invoiced, it is
        cancelled. It lives here and not on the button: "Cancel" from the list (the
        native wizard) and the portal call this method directly."""
        moved = self.filtered(
            lambda order: any(
                not line.product_uom_id.is_zero(line.qty_delivered)
                or not line.product_uom_id.is_zero(line.qty_invoiced)
                for line in order.order_line
                if not line.display_type
            )
        )
        if moved:
            raise UserError(
                self.env._(
                    "%(orders)s already has goods delivered or invoiced: it is not "
                    "cancelled. To undo it, return the "
                    "goods and create the credit note from the order; with nothing "
                    "delivered or invoiced, it can be "
                    "cancelled.",
                    orders=", ".join(moved.mapped("name")),
                )
            )
        return super()._action_cancel()

    def action_confirm(self):
        """What was confirmed with differences (the portal, an automated process or
        with the exceptions ignored) stays in the note of the order; if nobody saw
        it, also in an activity for its salesperson."""
        automatic = self._bl_confirms_without_brakes()
        notes = {}
        for order in self:
            texts = order._bl_confirmation_differences()
            if texts and (automatic or order.ignore_exception):
                notes[order] = texts
        res = super().action_confirm()
        for order, texts in notes.items():
            body = Markup("<p>{}</p><ul>{}</ul>").format(
                self.env._("Confirmed with differences:"),
                Markup().join(Markup("<li>{}</li>").format(text) for text in texts),
            )
            order.message_post(body=body, subtype_xmlid="mail.mt_note")
            if automatic and order.user_id:
                order.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=self.env._("Order confirmed with differences"),
                    note=body,
                    user_id=order.user_id.id,
                )
        return res

    def action_bl_update_prices(self):
        """ "Update Prices" of the expired quotation: today's prices, with the same
        recalculation Odoo runs when the pricelist changes (it leaves out the
        shipping and recalculates the promotions), today's date so that dated price
        rules apply, and a new expiration like a new quotation's (the days of the
        company or of its template). Manual prices and discounts go back to the
        pricelist's, as when the pricelist changes; the pricelist does not
        recalculate the shipping: it is flagged to be updated with the native button.
        The total before and after stays in the history. While the quotation is
        valid, its prices hold: it is not updated."""
        for order in self:
            if not order.is_expired:
                raise UserError(
                    self.env._(
                        "%(order)s is not an expired quotation: its prices still hold.",
                        order=order.name,
                    )
                )
            before = order.amount_total
            order.date_order = fields.Datetime.now()
            order._recompute_prices()
            order._compute_validity_date()
            if order.order_line.filtered("is_delivery"):
                # the pricelist does not recalculate the shipping: Odoo offers to update
                # it with its usual button
                order.recompute_delivery_price = True
            # the native "Expired" is computed without dependencies: without this, it
            # would stay expired in the same transaction
            order.invalidate_recordset(["is_expired"])
            order.message_post(
                body=self.env._(
                    "Prices updated to today with the pricelist (manual prices and "
                    "discounts were replaced): the "
                    "total went from %(before)s to %(after)s; the quotation is valid "
                    "until %(validity)s.",
                    before=formatLang(self.env, before, currency_obj=order.currency_id),
                    after=formatLang(
                        self.env, order.amount_total, currency_obj=order.currency_id
                    ),
                    validity=format_date(self.env, order.validity_date)
                    if order.validity_date
                    else "-",
                )
            )
        return True

    def _bl_check_sales_manager(self, action):
        """Ignoring the restrictions and unlocking a confirmed order belong to the
        Sales administrator (and to support, the system administrator): Odoo and the
        exception engine ask for it only on the button, and any salesperson could do
        it through the API. What runs as the system (sudo) stays the same."""
        user = self.env.user
        if (
            self.env.su
            or user.has_group("sales_team.group_sale_manager")
            or user.has_group("base.group_system")
        ):
            return
        raise AccessError(
            self.env._("Only a Sales administrator can %(action)s.", action=action)
        )

    def action_ignore_exceptions(self):
        self._bl_check_sales_manager(self.env._("ignore the exceptions of an order"))
        return super().action_ignore_exceptions()

    def action_unlock(self):
        self._bl_check_sales_manager(self.env._("unlock a confirmed order"))
        return super().action_unlock()

    def write(self, vals):
        # setting "Ignore Exceptions" by hand is the same as the button; clearing it
        # (back to draft) is not stopped
        if vals.get("ignore_exception"):
            self._bl_check_sales_manager(
                self.env._("ignore the exceptions of an order")
            )
        # unlocking by hand is the same as "Unlock"; a subscription that reopens is
        # unlocked by its own process
        if "locked" in vals and not vals["locked"]:
            locked = self.filtered("locked")
            if "subscription_state" in self._fields:
                locked = locked.filtered(lambda order: not order.subscription_state)
            if locked:
                self._bl_check_sales_manager(self.env._("unlock a confirmed order"))
        return super().write(vals)
