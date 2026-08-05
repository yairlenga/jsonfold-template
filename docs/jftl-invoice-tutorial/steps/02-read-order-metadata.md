# Step 2: Read order metadata

Replace only the order identifier and date with navigation expressions. The rest of the report remains static. `$.order_id` and `$.date` read properties from the current input document.

## Input

This step uses [`order.json`](../data/order.json).

## Template

```json
{
  "main": {
    "title": "Invoice Report",
    "order_id": "$.order_id",
    "date": "$.date",
    "customer": {
      "company": "Northwind Research",
      "contact": "Maria Anders",
      "address": "14 Lake Street, Boston, MA 02110, US"
    },
    "items": [
      {
        "product_id": "P-100",
        "description": "USB-C Dock",
        "quantity": 2,
        "unit_price": 129.95,
        "unit_weight": 0.85,
        "line_total": 259.9,
        "line_weight": 1.7
      },
      {
        "product_id": "P-205",
        "description": "Wireless Keyboard",
        "quantity": 1,
        "unit_price": 74.5,
        "unit_weight": 0.62,
        "line_total": 74.5,
        "line_weight": 0.62
      },
      {
        "product_id": "P-310",
        "description": "27-inch Monitor",
        "quantity": 1,
        "unit_price": 289.0,
        "unit_weight": 4.8,
        "line_total": 289.0,
        "line_weight": 4.8
      }
    ],
    "subtotal": 623.4,
    "total_weight": 7.12
  }
}
```

Runnable file: [`02-read-order-metadata.template.json`](02-read-order-metadata.template.json)

## Run it

```bash
jf-template 02-read-order-metadata.template.json ../data/order.json
```

## Output

```json
{
  "title": "Invoice Report",
  "order_id": "ORD-1001",
  "date": "2026-08-01",
  "customer": {
    "company": "Northwind Research",
    "contact": "Maria Anders",
    "address": "14 Lake Street, Boston, MA 02110, US"
  },
  "items": [
    {
      "product_id": "P-100",
      "description": "USB-C Dock",
      "quantity": 2,
      "unit_price": 129.95,
      "unit_weight": 0.85,
      "line_total": 259.9,
      "line_weight": 1.7
    },
    {
      "product_id": "P-205",
      "description": "Wireless Keyboard",
      "quantity": 1,
      "unit_price": 74.5,
      "unit_weight": 0.62,
      "line_total": 74.5,
      "line_weight": 0.62
    },
    {
      "product_id": "P-310",
      "description": "27-inch Monitor",
      "quantity": 1,
      "unit_price": 289.0,
      "unit_weight": 4.8,
      "line_total": 289.0,
      "line_weight": 4.8
    }
  ],
  "subtotal": 623.4,
  "total_weight": 7.12
}
```

Expected output: [`02-read-order-metadata.output.json`](02-read-order-metadata.output.json)

## What became dynamic

Order ID and date.

---

← [Start with a static invoice](01-start-with-a-static-invoice.md) | [Tutorial index](../README.md) | [Add inline support datasets](03-add-inline-support-datasets.md) →
