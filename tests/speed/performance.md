# Performance Test
- Measuring best of 5.

## foreach1m - Loop Over 1M range

### foreach1m-1 (iterate 1M times, loop body disabled)
- 0.2.4 (2026-08-01): 1.19
- 0.3.1 (2026-08-03): 0.69
- 0.3.2 (2026-08-04): 0.26
- 0.3.5 (2026-08-07): 0.211

### foreach1m-2 (iterate 1M times, Pass-thru)
- 0.3.2: (2026-08-04): 0.38
- 0.3.5: (2026-08-07): 0.23

### foreach1m-3 (iterate 1M times, return local variable)
- 0.3.2: (2026-08-04): 1.19
- 0.3.5: (2026-08-07): 1.06

### foreach1m-5 (iterate 1M times, return missing value)
- 0.3.5: (2026-08-07): 1.07

### foreach1m-6 (iterate 1M times, return 3 element object with variables)
- 0.3.4: (2026-08-07): 2.41


### foreach1m-7 (iterate 1M times, return 5 element object: including array nav, obj nav)
- 0.3.5: (2026-08-07): 5.25

## range1m (generate array 1M elements)

- 0.2.4 (2026-08-01): 1.50
- 0.3.1 (2026-08-03): 0.87
- 0.3.1 (2026-08-03): 0.64
- 0.3.5 (2026-08-07): 0.21

## foreach-2 (1000 X 1000)
- 0.2.4 (2026-08-01): 1.47
- 0.3.1 (2026-08-03): 0.90
- 0.3.1 (2026-08-03): 0.67
- 0.3.5 (2026-08-07): 0.22