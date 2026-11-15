# Copyright 2026 Base Lógica (baselogica.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Interests with the Fiscal Position of the Overdue Invoice",
    "summary": "The late payment interest note carries the VAT of the overdue invoices "
    "it charges, not the one of the customer's form.",
    "version": "20.0.1.0.0",
    "category": "Accounting/Accounting",
    "author": "Base Lógica",
    "website": "https://github.com/baselogica-ar/baselogica-open-addons",
    "license": "AGPL-3",
    "development_status": "Beta",
    "depends": ["account_interests"],
    # wherever the interests module is, its note follows the overdue invoices
    "auto_install": True,
}
