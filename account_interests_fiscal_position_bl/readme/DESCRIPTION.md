The late payment interest of the Odoo community (`account_interests`) makes, each
period, a debit note with the interest of what each customer owes. The note takes its
fiscal position, and with it its VAT, from the customer's form. When the form no longer
says how the overdue invoices were made, the note goes out with another VAT: a customer
that buys now without VAT and still owes an invoice made with VAT gets a note without
VAT, and the other way round. The interest is part of the price of the sale paid late,
so it carries the VAT of that sale.

This module makes the note follow the invoices it charges:

- **The fiscal position of the overdue invoices**: the note takes the one of the
  invoices whose interest it charges (the ones still overdue and, with late payment
  interest, the ones paid late in the period), not the one of the customer's form.
- **Several fiscal positions**: when the overdue invoices of a customer in the same
  company have different ones, which normal work does not make, the note takes the one
  of the largest part of the debt.
- **The taxes, as on an invoice**: the taxes of the interest product, mapped by that
  fiscal position. A branch without taxes of its own uses the ones of its parent
  company, as Odoo does on its invoices: without this module, the note of a branch goes
  out without taxes.
- **Nothing else changes**: the amounts, the lines, the journal, the document type and
  the validation stay as the interests module makes them.
