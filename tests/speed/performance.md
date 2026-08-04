# Performance Test

## foreach1m - Loop Over 1M range

### foreach1m-1 (iterate 1M times, loop body disabled)

- 0.2.4 (2026-08-01): 1.196
- 0.3.1 (2026-08-03): 0.697
- 0.3.2 (2026-08-04): 0.261

### foreach1m-2 (iterate 1M times, Pass-thru)
- 0.3.2: (2026-08-04): 0.388

### foreach1m-3 (iterate 1M times, return local variable)
- 0.3.2: (2026-08-04): 1.190


## range1m (generate array 1M elements)

- 0.2.4 (2026-08-01): 1.509
- 0.3.1 (2026-08-03): 0.871
- 0.3.1 (2026-08-03): 0.647

## foreach2 (1000 X 1000)

- 0.2.4 (2026-08-01): 1.479
- 0.3.1 (2026-08-03): 0.903
- 0.3.1 (2026-08-03): 0.676