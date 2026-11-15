# Copyright 2026 Base Lógica (baselogica.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestInterestFiscalPosition(AccountTestInvoicingCommon):
    """The interest note takes the fiscal position of the overdue invoices it charges,
    not the one of the customer's form: the interest is part of the price of the sale
    paid late, so it carries that sale's VAT. Its taxes are the ones of the interest
    product, picked as Odoo picks them on an invoice: a branch uses the ones of its
    parent company."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.branch = cls._create_company(name="Branch", parent_id=cls.company.id)
        # the end of the period of the next run of each rule, today, as the scheduled
        # action runs it
        cls.to_date = fields.Date.today()
        Tax = cls.env["account.tax"]
        Position = cls.env["account.fiscal.position"]
        cls.tax_vat = Tax.create(
            {
                "name": "VAT 21% of the interest",
                "amount": 21.0,
                "type_tax_use": "sale",
                "company_id": cls.company.id,
            }
        )
        cls.position_domestic = Position.create(
            {"name": "Domestic", "company_id": cls.company.id}
        )
        cls.position_without_vat = Position.create(
            {"name": "Without VAT", "company_id": cls.company.id}
        )
        cls.tax_without_vat = Tax.create(
            {
                "name": "Without VAT",
                "amount": 0.0,
                "type_tax_use": "sale",
                "company_id": cls.company.id,
                "fiscal_position_ids": [Command.set(cls.position_without_vat.ids)],
                "original_tax_ids": [Command.set(cls.tax_vat.ids)],
            }
        )
        cls.interest_product = cls.env["product.product"].create(
            {
                "name": "Late payment interest",
                "type": "service",
                "list_price": 0.0,
                "taxes_id": [Command.set(cls.tax_vat.ids)],
            }
        )
        cls.rule = cls._create_rule(cls.company)
        cls.branch_rule = cls._create_rule(cls.branch)

    @classmethod
    def _create_rule(cls, company):
        """A rule of each company sweeps only its own invoices, by its filter: the
        receivable account is shared by the company and its branches."""
        receivable = cls.env["account.account"].search(
            [
                ("account_type", "=", "asset_receivable"),
                *cls.env["account.account"]._check_company_domain(company),
            ]
        )
        return cls.env["res.company.interest"].create(
            {
                "company_id": company.id,
                "receivable_account_ids": [Command.set(receivable.ids)],
                "interest_product_id": cls.interest_product.id,
                "rate": 0.03,
                "past_due_rate": 0.03,
                "rule_type": "monthly",
                "interval": 1,
                "next_date": cls.to_date,
                "automatic_validation": False,
                "domain": f"[('company_id', '=', {company.id})]",
            }
        )

    def setUp(self):
        super().setUp()
        # the interests module commits between batches, which the test cursor forbids
        self.patch(self.env.cr, "commit", lambda: None)

    def _customer(self, name, position=None):
        customer = self.env["res.partner"].create({"name": name})
        if position:
            customer.with_company(self.company).property_account_position_id = position
        return customer

    def _invoice(self, customer, position, amount=1000.0, company=None, days=10):
        """An invoice made with the fiscal position and the taxes of that sale, due
        `days` days before the end of the period."""
        company = company or self.company
        due = self.to_date - relativedelta(days=days)
        invoice = (
            self.env["account.move"]
            .with_company(company)
            .create(
                {
                    "move_type": "out_invoice",
                    "company_id": company.id,
                    "partner_id": customer.id,
                    "fiscal_position_id": position.id,
                    "invoice_date": due,
                    "invoice_date_due": due,
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "name": "Goods",
                                "quantity": 1,
                                "price_unit": amount,
                                "tax_ids": [
                                    Command.set(position.map_tax(self.tax_vat).ids)
                                ],
                            }
                        )
                    ],
                }
            )
        )
        invoice.action_post()
        return invoice

    def _note(self, customer, rule=None):
        (rule or self.rule).create_interest_invoices()
        return self.env["account.move"].search(
            [
                ("partner_id", "=", customer.id),
                ("invoice_origin", "=", "Interests Invoice"),
            ]
        )

    def test_note_takes_the_vat_of_the_overdue_invoice(self):
        """The customer's form says Without VAT, but its overdue invoice was made with
        VAT (it bought before its form changed): the note carries that VAT."""
        customer = self._customer("Customer now without VAT")
        self._invoice(customer, self.position_domestic)
        customer.with_company(
            self.company
        ).property_account_position_id = self.position_without_vat
        note = self._note(customer)
        self.assertEqual(note.fiscal_position_id, self.position_domestic)
        self.assertEqual(note.invoice_line_ids.tax_ids, self.tax_vat)
        self.assertGreater(note.amount_tax, 0)

    def test_note_without_vat_for_an_invoice_without_vat(self):
        """The other way round: the form has no fiscal position and the overdue invoice
        was made without VAT, so the note goes without VAT."""
        customer = self._customer("Customer of an invoice without VAT")
        self._invoice(customer, self.position_without_vat)
        note = self._note(customer)
        self.assertEqual(note.fiscal_position_id, self.position_without_vat)
        self.assertEqual(note.invoice_line_ids.tax_ids, self.tax_without_vat)
        self.assertEqual(note.amount_tax, 0)

    def test_several_positions_take_the_largest_debt(self):
        """Overdue invoices of the same customer and company with different VAT, which
        normal work does not make: the note takes the fiscal position of the largest
        part of the debt."""
        customer = self._customer("Customer with two kinds of invoices")
        self._invoice(customer, self.position_domestic, amount=300.0)
        self._invoice(customer, self.position_without_vat, amount=1000.0)
        note = self._note(customer)
        self.assertEqual(note.fiscal_position_id, self.position_without_vat)
        self.assertEqual(note.invoice_line_ids.tax_ids, self.tax_without_vat)

    def test_late_payment_takes_the_invoice_paid_late(self):
        """Interest on a payment made after the due date, with nothing left to pay: the
        note takes the fiscal position of the invoice paid late."""
        self.rule.late_payment_interest = True
        customer = self._customer("Customer that paid late")
        invoice = self._invoice(customer, self.position_without_vat, days=20)
        self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=invoice.ids
        ).create(
            {
                "payment_date": self.to_date - relativedelta(days=5),
                "amount": invoice.amount_residual,
            }
        ).action_create_payments()
        self.assertEqual(invoice.payment_state, "paid")
        note = self._note(customer)
        self.assertEqual(note.fiscal_position_id, self.position_without_vat)
        self.assertEqual(note.invoice_line_ids.tax_ids, self.tax_without_vat)

    def test_branch_uses_the_taxes_of_its_parent(self):
        """A branch without taxes of its own invoices with the ones of its parent
        company: its interest note keeps the VAT of the overdue invoice."""
        customer = self._customer("Customer of the branch")
        self._invoice(customer, self.position_domestic, company=self.branch)
        note = self._note(customer, self.branch_rule)
        self.assertEqual(note.company_id, self.branch)
        self.assertEqual(note.fiscal_position_id, self.position_domestic)
        self.assertEqual(note.invoice_line_ids.tax_ids, self.tax_vat)
        self.assertGreater(note.amount_tax, 0)

    def test_branch_without_vat_carries_the_tax_of_its_invoices(self):
        """A branch that invoices without VAT: its interest note carries the same tax
        as its invoices, mapped from the one of its parent company."""
        customer = self._customer("Customer of the branch without VAT")
        self._invoice(customer, self.position_without_vat, company=self.branch)
        note = self._note(customer, self.branch_rule)
        self.assertEqual(note.fiscal_position_id, self.position_without_vat)
        self.assertEqual(note.invoice_line_ids.tax_ids, self.tax_without_vat)

    def test_each_company_charges_its_own_invoices(self):
        """A customer that owes the company and its branch gets one note from each,
        each with the fiscal position of its own invoices."""
        customer = self._customer("Customer of both")
        self._invoice(customer, self.position_domestic)
        self._invoice(customer, self.position_without_vat, company=self.branch)
        self.rule.create_interest_invoices()
        notes = self._note(customer, self.branch_rule)
        self.assertEqual(len(notes), 2)
        of_company = notes.filtered(lambda note: note.company_id == self.company)
        of_branch = notes - of_company
        self.assertEqual(of_company.invoice_line_ids.tax_ids, self.tax_vat)
        self.assertEqual(of_branch.invoice_line_ids.tax_ids, self.tax_without_vat)

    def test_nothing_to_read_keeps_the_form(self):
        """Called without overdue invoices behind it, the note keeps the fiscal position
        of the customer's form, as the interests module does."""
        customer = self._customer(
            "Customer without invoices", self.position_without_vat
        )
        vals = self.rule.with_company(self.company)._prepare_interest_invoice(
            customer,
            {"Deuda último periodo": 10.0},
            self.to_date,
            self.company_data["default_journal_sale"],
        )
        self.assertEqual(vals["fiscal_position_id"], self.position_without_vat.id)
        self.assertEqual(
            vals["invoice_line_ids"][0][2]["tax_ids"],
            [Command.set(self.tax_without_vat.ids)],
        )
