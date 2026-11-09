- On each customer that works with purchase orders: Sales & Purchase → Purchase Order
  Required (set on the company; its branches and addresses follow it).
- On each pickup delivery method: Customer Collects.
- The rules, in Sales → Configuration → Sale Exception Rules: a Sales administrator
  archives the ones not used (a company that sells goods counted in units in fractions
  archives "Quantity with decimals"); a Settings administrator makes blocking the ones nobody may
  ignore, and creates new rules with a filter.
- To stop the orders over the credit limit: Accounting → Configuration → Settings → Sales
  Credit Limit, with its Default Credit Limit, and each customer's own limit in its form
  (Credit Limits); then, in Sale Exception Rules, the "Archived" filter and "Unarchive" on
  "Customer over its credit limit".
