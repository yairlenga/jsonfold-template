# Step 13: Process multiple orders

Change the input to an array of orders and add one outer `foreach`. Its per-item output is the already-complete single-order transformation. The invoice logic itself is unchanged; the outer loop only applies it repeatedly.

## Input

This step uses [`orders.json`](../data/orders.json).

## Template

```json
{
  "config": {
    "default_expr_engine": "py"
  },
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
    "foreach": {
      "in": "$",
      "value": "order",
      "out": {
        "$": true,
        "set": {
          "customer_id": "$.customer_id",
          "customer": "$_datasets.customers[$customer_id]",
          "lines": {
            "$": true,
            "set": {
              "subtotal": 0,
              "total_weight": 0
            },
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
                  "line_total": "$=item[\"quantity\"] * product[\"unit_price\"]",
                  "line_weight": "$=item[\"quantity\"] * product[\"weight\"]"
                }
              },
              "update": {
                "subtotal": "$=subtotal + _[\"line_total\"]",
                "total_weight": "$=total_weight + _[\"line_weight\"]"
              }
            },
            "out": {
              "items": "$",
              "subtotal": "$subtotal",
              "total_weight": "$total_weight"
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
          "items": "$lines.items",
          "subtotal": "$lines.subtotal",
          "total_weight": "$lines.total_weight"
        },
        "data": "$order"
      }
    }
  }
}
```

Runnable file: [`13-process-multiple-orders.template.json`](13-process-multiple-orders.template.json)

## Run it

```bash
jf-template 13-process-multiple-orders.template.json ../data/orders.json
```

## Output

```json
[
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
    "total_weight": 7.119999999999999
  },
  {
    "title": "Invoice Report",
    "order_id": "ORD-1002",
    "date": "2026-08-02",
    "customer": {
      "company": "Acme Manufacturing",
      "contact": "Daniel Reed",
      "address": "81 Industrial Road, Chicago, IL 60601, US"
    },
    "items": [
      {
        "product_id": "P-205",
        "description": "Wireless Keyboard",
        "quantity": 2,
        "unit_price": 74.5,
        "unit_weight": 0.62,
        "line_total": 149.0,
        "line_weight": 1.24
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
    "subtotal": 438.0,
    "total_weight": 6.04
  }
]
```

Expected output: [`13-process-multiple-orders.output.json`](13-process-multiple-orders.output.json)

## What became dynamic

Number of invoices and all fields in each invoice.

---

← [Review the completed one-order conversion](12-review-the-completed-one-order-conversion.md) | [Tutorial index](../README.md) | [Move datasets to separate files](14-move-datasets-to-separate-files.md) →
