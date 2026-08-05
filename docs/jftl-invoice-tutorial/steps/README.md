# JFTL Invoice Tutorial

This tutorial builds one invoice-style JSON report from an order, then generalizes the completed conversion to multiple orders. Each step starts from the previous working template and replaces a small amount of static data with navigation, dataset lookups, interpolation, iteration, expressions, or aggregation.

## Scenario

The order contains only an order ID, date, customer ID, product IDs, and quantities. Two support tables provide customer and product details. The final report combines all three sources and calculates line amounts, invoice subtotal, line weights, and total shipment weight. Product weights are expressed in kilograms.

## Files

- `data/order.json` — the single order used in Steps 1–12.
- `data/orders.json` — two orders used in Steps 13–14.
- `data/customers.json` — customer support table.
- `data/products.json` — product support table.
- `steps/*.template.json` — runnable template for each step.
- `steps/*.output.json` — expected output for each step.
- `steps/*.md` — explanation, full template, command, and output.

## Tutorial sequence

1. [Start with a static invoice](steps/01-start-with-a-static-invoice.md)
2. [Read order metadata](steps/02-read-order-metadata.md)
3. [Add inline support datasets](steps/03-add-inline-support-datasets.md)
4. [Look up the customer](steps/04-look-up-the-customer.md)
5. [Build the contact name](steps/05-build-the-contact-name.md)
6. [Build the mailing address](steps/06-build-the-mailing-address.md)
7. [Generate one line per order item](steps/07-generate-one-line-per-order-item.md)
8. [Enrich lines from the product dataset](steps/08-enrich-lines-from-the-product-dataset.md)
9. [Calculate line amount and weight](steps/09-calculate-line-amount-and-weight.md)
10. [Accumulate the subtotal](steps/10-accumulate-the-subtotal.md)
11. [Accumulate total weight](steps/11-accumulate-total-weight.md)
12. [Review the completed one-order conversion](steps/12-review-the-completed-one-order-conversion.md)
13. [Process multiple orders](steps/13-process-multiple-orders.md)
14. [Move datasets to separate files](steps/14-move-datasets-to-separate-files.md)

## Running the examples

Run commands from the `steps` directory. Steps 1–13 use datasets embedded in the template. Step 14 demonstrates external datasets with `-F`.

```bash
cd steps
jf-template 01-start-with-a-static-invoice.template.json ../data/order.json
```

The templates use the safe `py` expression engine only when arithmetic is introduced.

## Learning progression

| Step | New capability |
|---:|---|
| 1 | Required `main` entry and literal JSON |
| 2 | Navigation from the current input |
| 3 | Inline datasets |
| 4 | Logic element, `set`, and dynamic dataset lookup |
| 5 | Interpolation |
| 6 | Interpolation reinforcement |
| 7 | First `foreach` |
| 8 | Product lookup inside iteration |
| 9 | Default expression engine and arithmetic |
| 10 | `update` and one accumulator |
| 11 | Multiple accumulators |
| 12 | Complete one-order checkpoint |
| 13 | Outer `foreach` for multiple orders |
| 14 | CLI-supplied datasets |
