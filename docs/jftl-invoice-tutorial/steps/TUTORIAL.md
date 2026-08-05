# JFTL Invoice Tutorial — Single-Page Edition

This file combines the linked tutorial chapters. The runnable JSON files remain under `steps/` and `data/`.


---

## Step 1: Start with a static invoice

A JFTL template is a JSON document with a required `main` entry. Ordinary JSON values are literal, so this first template ignores the input and returns a complete but fully static invoice.

## Input

This step uses [`order.json`](data/order.json).

## Template

```json
{
  "main": {
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
}
```

Runnable file: [`01-start-with-a-static-invoice.template.json`](steps/01-start-with-a-static-invoice.template.json)

## Run it

```bash
jf-template 01-start-with-a-static-invoice.template.json ../data/order.json
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

Expected output: [`01-start-with-a-static-invoice.output.json`](steps/01-start-with-a-static-invoice.output.json)

## What became dynamic

Nothing yet. The complete report is literal JSON.

---

## Step 2: Read order metadata

Replace only the order identifier and date with navigation expressions. The rest of the report remains static. `$.order_id` and `$.date` read properties from the current input document.

## Input

This step uses [`order.json`](data/order.json).

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

Runnable file: [`02-read-order-metadata.template.json`](steps/02-read-order-metadata.template.json)

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

Expected output: [`02-read-order-metadata.output.json`](steps/02-read-order-metadata.output.json)

## What became dynamic

Order ID and date.

---

## Step 3: Add inline support datasets

Add customer and product lookup tables under the optional `datasets` entry. The report does not use them yet, so the output is unchanged. During rendering they are available through the built-in `_datasets` value.

## Input

This step uses [`order.json`](data/order.json).

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

Runnable file: [`03-add-inline-support-datasets.template.json`](steps/03-add-inline-support-datasets.template.json)

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

Expected output: [`03-add-inline-support-datasets.output.json`](steps/03-add-inline-support-datasets.output.json)

## What became dynamic

No report field; support data is now available.

---

## Step 4: Look up the customer

Turn `main` into a logic element. `set` stores the order's customer ID and then resolves the corresponding customer record. Only the company field becomes dynamic in this step; contact and address remain static.

## Input

This step uses [`order.json`](data/order.json).

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
}
```

Runnable file: [`04-look-up-the-customer.template.json`](steps/04-look-up-the-customer.template.json)

## Run it

```bash
jf-template 04-look-up-the-customer.template.json ../data/order.json
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

Expected output: [`04-look-up-the-customer.output.json`](steps/04-look-up-the-customer.output.json)

## What became dynamic

Customer company.

---

## Step 5: Build the contact name

Replace the static contact name with interpolation. The two customer fields are evaluated and concatenated with the literal space between them.

## Input

This step uses [`order.json`](data/order.json).

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
}
```

Runnable file: [`05-build-the-contact-name.template.json`](steps/05-build-the-contact-name.template.json)

## Run it

```bash
jf-template 05-build-the-contact-name.template.json ../data/order.json
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

Expected output: [`05-build-the-contact-name.output.json`](steps/05-build-the-contact-name.output.json)

## What became dynamic

Customer contact name.

---

## Step 6: Build the mailing address

Use interpolation again to combine the individual address parts. This step introduces no new syntax; it reinforces interpolation with a longer value.

## Input

This step uses [`order.json`](data/order.json).

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

Runnable file: [`06-build-the-mailing-address.template.json`](steps/06-build-the-mailing-address.template.json)

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

Expected output: [`06-build-the-mailing-address.output.json`](steps/06-build-the-mailing-address.output.json)

## What became dynamic

Customer address.

---

## Step 7: Generate one line per order item

Replace the literal item array with the first `foreach`. The loop reads `$.items`, binds each entry to `item`, and emits one report line. Only `product_id` and `quantity` are dynamic; the remaining line fields are deliberately still static.

## Input

This step uses [`order.json`](data/order.json).

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
            "product_id": "$item.product_id",
            "description": "USB-C Dock",
            "quantity": "$item.quantity",
            "unit_price": 129.95,
            "unit_weight": 0.85,
            "line_total": 259.9,
            "line_weight": 1.7
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

Runnable file: [`07-generate-one-line-per-order-item.template.json`](steps/07-generate-one-line-per-order-item.template.json)

## Run it

```bash
jf-template 07-generate-one-line-per-order-item.template.json ../data/order.json
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
      "description": "USB-C Dock",
      "quantity": 1,
      "unit_price": 129.95,
      "unit_weight": 0.85,
      "line_total": 259.9,
      "line_weight": 1.7
    },
    {
      "product_id": "P-310",
      "description": "USB-C Dock",
      "quantity": 1,
      "unit_price": 129.95,
      "unit_weight": 0.85,
      "line_total": 259.9,
      "line_weight": 1.7
    }
  ],
  "subtotal": 623.4,
  "total_weight": 7.12
}
```

Expected output: [`07-generate-one-line-per-order-item.output.json`](steps/07-generate-one-line-per-order-item.output.json)

## What became dynamic

Number of lines, product IDs, and quantities.

---

## Step 8: Enrich lines from the product dataset

For each order line, resolve the product record by `product_id`. Description, unit price, and unit weight now come from the product dataset. The calculated fields remain static for one more step.

## Input

This step uses [`order.json`](data/order.json).

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

Runnable file: [`08-enrich-lines-from-the-product-dataset.template.json`](steps/08-enrich-lines-from-the-product-dataset.template.json)

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

Expected output: [`08-enrich-lines-from-the-product-dataset.output.json`](steps/08-enrich-lines-from-the-product-dataset.output.json)

## What became dynamic

Product descriptions, unit prices, and unit weights.

---

## Step 9: Calculate line amount and weight

Choose `py` as the default expression engine, then use `$=...` expressions to calculate each line's amount and weight. The invoice-level totals are still static.

## Input

This step uses [`order.json`](data/order.json).

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
              "line_total": "$=item[\"quantity\"] * product[\"unit_price\"]",
              "line_weight": "$=item[\"quantity\"] * product[\"weight\"]"
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

Runnable file: [`09-calculate-line-amount-and-weight.template.json`](steps/09-calculate-line-amount-and-weight.template.json)

## Run it

```bash
jf-template 09-calculate-line-amount-and-weight.template.json ../data/order.json
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

Expected output: [`09-calculate-line-amount-and-weight.output.json`](steps/09-calculate-line-amount-and-weight.output.json)

## What became dynamic

Line totals and line weights.

---

## Step 10: Accumulate the subtotal

Initialize `subtotal`, update it after each emitted line, and return both the collected lines and the completed subtotal from the nested logic element. The invoice now reads its subtotal from that result bundle.

## Input

This step uses [`order.json`](data/order.json).

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
    "set": {
      "customer_id": "$.customer_id",
      "customer": "$_datasets.customers[$customer_id]",
      "lines": {
        "$": true,
        "set": {
          "subtotal": 0
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
            "subtotal": "$=subtotal + _[\"line_total\"]"
          }
        },
        "out": {
          "items": "$",
          "subtotal": "$subtotal"
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
      "total_weight": 7.12
    }
  }
}
```

Runnable file: [`10-accumulate-the-subtotal.template.json`](steps/10-accumulate-the-subtotal.template.json)

## Run it

```bash
jf-template 10-accumulate-the-subtotal.template.json ../data/order.json
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

Expected output: [`10-accumulate-the-subtotal.output.json`](steps/10-accumulate-the-subtotal.output.json)

## What became dynamic

Invoice subtotal.

---

## Step 11: Accumulate total weight

Add a second accumulator using the same `update` mechanism. At this point every business value in the single-order invoice is derived from the order or a support dataset.

## Input

This step uses [`order.json`](data/order.json).

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
    }
  }
}
```

Runnable file: [`11-accumulate-total-weight.template.json`](steps/11-accumulate-total-weight.template.json)

## Run it

```bash
jf-template 11-accumulate-total-weight.template.json ../data/order.json
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

Expected output: [`11-accumulate-total-weight.output.json`](steps/11-accumulate-total-weight.output.json)

## What became dynamic

Total invoice weight.

---

## Step 12: Review the completed one-order conversion

This checkpoint introduces no new syntax. It presents the complete one-order transformation as a whole before the tutorial generalizes it to an array of orders.

## Input

This step uses [`order.json`](data/order.json).

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
    }
  }
}
```

Runnable file: [`12-review-the-completed-one-order-conversion.template.json`](steps/12-review-the-completed-one-order-conversion.template.json)

## Run it

```bash
jf-template 12-review-the-completed-one-order-conversion.template.json ../data/order.json
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

Expected output: [`12-review-the-completed-one-order-conversion.output.json`](steps/12-review-the-completed-one-order-conversion.output.json)

## What became dynamic

All fields for one order.

---

## Step 13: Process multiple orders

Change the input to an array of orders and add one outer `foreach`. Its per-item output is the already-complete single-order transformation. The invoice logic itself is unchanged; the outer loop only applies it repeatedly.

## Input

This step uses [`orders.json`](data/orders.json).

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

Runnable file: [`13-process-multiple-orders.template.json`](steps/13-process-multiple-orders.template.json)

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

Expected output: [`13-process-multiple-orders.output.json`](steps/13-process-multiple-orders.output.json)

## What became dynamic

Number of invoices and all fields in each invoice.

---

## Step 14: Move datasets to separate files

Remove the inline `datasets` entry and provide the same named datasets through the CLI. This is usually more practical for large or independently maintained support tables.

## Input

This step uses [`orders.json`](data/orders.json).

## Template

```json
{
  "config": {
    "default_expr_engine": "py"
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

Runnable file: [`14-move-datasets-to-separate-files.template.json`](steps/14-move-datasets-to-separate-files.template.json)

## Run it

```bash
jf-template -F customers ../data/customers.json -F products ../data/products.json 14-move-datasets-to-separate-files.template.json ../data/orders.json
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

Expected output: [`14-move-datasets-to-separate-files.output.json`](steps/14-move-datasets-to-separate-files.output.json)

## What became dynamic

No output change; datasets are supplied externally.
