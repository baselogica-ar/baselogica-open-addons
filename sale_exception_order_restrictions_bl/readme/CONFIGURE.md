- On each customer that works with purchase orders: Sales & Purchase → Purchase Order
  Required (set on the company; its branches and addresses follow it).
- On each pickup delivery method: Customer Collects.
- The rules, in Sales → Configuration → Sales Orders → Sale Exception Rules: a Sales
  administrator turns off the ones not used with their Active toggle (a company that sells
  goods counted in units in fractions turns off "Quantity with decimals"); a Settings
  administrator makes blocking the ones nobody may ignore, and creates new rules with a
  filter.
- To stop the orders over the credit limit: Accounting → Configuration → Settings → Sales
  Credit Limit, with its Default Credit Limit, and each customer's own limit in its form
  (Credit Limits); then, in Sale Exception Rules, a Sales administrator turns on "Customer
  over its credit limit" with its Active toggle (the list shows the rules on and off).
