# Copyright 2026 Base Lógica (baselogica.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""What it changes of the interests module of the Odoo community (account_interests):
the fiscal position and the taxes of the interest note. That module takes the fiscal
position of the customer's form and only the taxes of the interest product that belong
to the company itself; this one takes the fiscal position of the overdue invoices the
note charges, and the taxes the way Odoo picks them on an invoice (a branch uses the
ones of its parent company). It is retired when account_interests does the same."""

from . import models
