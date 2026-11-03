The sales order is not confirmed while something sets it apart from the customer's form,
until it is fixed or a Sales administrator ignores its exceptions. Each restriction is a
rule of the sale exception engine:

- **Payment terms** other than the ones of the customer's form.
- **Delivery method**: an order with goods and no delivery method, or with another method
  than the one of its delivery address or its company. A method where the customer
  collects the goods (a pickup) is valid for any address.
- **Customer's purchase order**: a customer marked "Purchase Order Required" needs its
  number in the Customer Reference.
- **Urgent order**, with the "Urgent" tag: a Sales administrator confirms it.
- **Expired quotation**: it is not confirmed with its old prices. "Update Prices", shown
  only on the expired quotation, brings today's prices with the same recalculation as
  changing the pricelist, today's date and a new expiration, and leaves the total before
  and after in the history.

Besides:

- Only a Sales administrator ignores the exceptions or unlocks a confirmed order, also
  through the API.
- The portal and automated processes are not stopped by any rule: the order is confirmed
  with the differences in its note and an activity for its salesperson.
- Confirmed orders are locked for everyone.
- An order with goods delivered or invoiced is not cancelled: it is undone with the return
  and the credit note.
