# Step 8: Enrich lines from the product dataset

For each order line, resolve the product record by `product_id`. Description, unit price, and unit weight now come from the product dataset. The calculated fields remain static for one more step.

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
      "customer": "$_datasets.customers[$customer_id]",
      "lines": {
        "$": true,
        "foreach": {
          "in": "$.items",
          "value": "item",
          "out": {
            "$": true,
            "set": {
              "product_id": "$item.product_id",
              "product": "$_datasets.products[$product_id]"
            },
            "out": {
              "product_id": "$item.product_id",
              "description": "$product.description",
              "quantity": "$item.quantity",
              "unit_price": "$product.unit_price",
              "unit_weight": "$product.weight",
              "line_total": 259.9,
              "line_weight": 1.7
            }
          }
        }
      }
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
      "items": "$lines",
      "subtotal": 623.4,
      "total_weight": 7.12
    }
  }
}
```

Runnable file: [`08-enrich-lines-from-the-product-dataset.template.json`](08-enrich-lines-from-the-product-dataset.template.json)

## Run it

```bash
jf-template 08-enrich-lines-from-the-product-dataset.template.json ../data/order.json
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
      "line_total": 259.9,
      "line_weight": 1.7
    },
    {
      "product_id": "P-310",
      "description": "27-inch Monitor",
      "quantity": 1,
      "unit_price": 289.0,
      "unit_weight": 4.8,
      "line_total": 259.9,
      "line_weight": 1.7
    }
  ],
  "subtotal": 623.4,
  "total_weight": 7.12
}
```

Expected output: [`08-enrich-lines-from-the-product-dataset.output.json`](08-enrich-lines-from-the-product-dataset.output.json)

## What became dynamic

Product descriptions, unit prices, and unit weights.

---

← [Generate one line per order item](07-generate-one-line-per-order-item.md) | [Tutorial index](../README.md) | [Calculate line amount and weight](09-calculate-line-amount-and-weight.md) →
