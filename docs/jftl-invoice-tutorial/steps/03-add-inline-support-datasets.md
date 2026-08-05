# Step 3: Add inline support datasets

Add customer and product lookup tables under the optional `datasets` entry. The report does not use them yet, so the output is unchanged. During rendering they are available through the built-in `_datasets` value.

## Input

This step uses [`order.json`](../data/order.json).

## Template

```json
{
  "datasets": {
    "customers": {
      "C-101": {
        "company": "Northwind Research",
        "contact": {
          "first_name": "Maria",
          "last_name": "Anders"
        },
        "address": {
          "street": "14 Lake Street",
          "city": "Boston",
          "zip": "02110",
          "state": "MA",
          "country": "US"
        }
      },
      "C-102": {
        "company": "Acme Manufacturing",
        "contact": {
          "first_name": "Daniel",
          "last_name": "Reed"
        },
        "address": {
          "street": "81 Industrial Road",
          "city": "Chicago",
          "zip": "60601",
          "state": "IL",
          "country": "US"
        }
      }
    },
    "products": {
      "P-100": {
        "description": "USB-C Dock",
        "unit_price": 129.95,
        "weight": 0.85
      },
      "P-205": {
        "description": "Wireless Keyboard",
        "unit_price": 74.5,
        "weight": 0.62
      },
      "P-310": {
        "description": "27-inch Monitor",
        "unit_price": 289.0,
        "weight": 4.8
      }
    }
  },
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

Runnable file: [`03-add-inline-support-datasets.template.json`](03-add-inline-support-datasets.template.json)

## Run it

```bash
jf-template 03-add-inline-support-datasets.template.json ../data/order.json
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

Expected output: [`03-add-inline-support-datasets.output.json`](03-add-inline-support-datasets.output.json)

## What became dynamic

No report field; support data is now available.

---

← [Read order metadata](02-read-order-metadata.md) | [Tutorial index](../README.md) | [Look up the customer](04-look-up-the-customer.md) →
