# Step 6: Build the mailing address

Use interpolation again to combine the individual address parts. This step introduces no new syntax; it reinforces interpolation with a longer value.

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
    "$": true,
    "set": {
      "customer_id": "$.customer_id",
      "customer": "$_datasets.customers[$customer_id]"
    },
    "out": {
      "title": "Invoice Report",
      "order_id": "$.order_id",
      "date": "$.date",
      "customer": {
        "company": "$customer.company",
        "contact": "${customer.contact.first_name} ${customer.contact.last_name}",
        "address": "${customer.address.street}, ${customer.address.city}, ${customer.address.state} ${customer.address.zip}, ${customer.address.country}"
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
}
```

Runnable file: [`06-build-the-mailing-address.template.json`](06-build-the-mailing-address.template.json)

## Run it

```bash
jf-template 06-build-the-mailing-address.template.json ../data/order.json
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

Expected output: [`06-build-the-mailing-address.output.json`](06-build-the-mailing-address.output.json)

## What became dynamic

Customer address.

---

← [Build the contact name](05-build-the-contact-name.md) | [Tutorial index](../README.md) | [Generate one line per order item](07-generate-one-line-per-order-item.md) →
