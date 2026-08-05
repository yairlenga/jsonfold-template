#!/bin/sh
set -eu
cd "$(dirname "$0")/steps"
for template in 0[1-9]-*.template.json 1[0-2]-*.template.json; do
  echo "== $template ==" >&2
  jf-template "$template" ../data/order.json >/dev/null
done
jf-template 13-process-multiple-orders.template.json ../data/orders.json >/dev/null
jf-template -F customers ../data/customers.json -F products ../data/products.json   14-move-datasets-to-separate-files.template.json ../data/orders.json >/dev/null
echo "All tutorial templates completed." >&2
