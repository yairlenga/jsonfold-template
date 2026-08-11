
0.3:
9.  (done) Fix handling of statements that evaluate to "null". They should return a reference to literal 
12. (done) Remove "shape" checks - after bundling it to condition.

0.4:

1. Navigation with JSON pointer
2. Navigation through objects methods ? Should be explicitly enabled
3. Add kind, `apiVersion`, and potentially schema to the top level
`isindex`, `isstring`, `isbool`, `isnumber`, `isint`, is null
5.  Named frames allowing reference to frame data - `foreach` block, lambda, (maybe, selected body)
6.  Iterators vs arrays.
7.  Recursion with lambdas: named lambdas, macro lambdas and labeled lambdas.
8.  (deferred) Reserve grammar for single argument function calls `foo:bar:baz` and `baz | bar | foo`
None. None will indicate no body.
10. Basic format for stringification of numbers - decimals, grouping, percent, 
11. Add condition specific prefixes: not: empty: null: array: object:, disallow plain values in condition.
13. Separate root name vs file name, may be

Long Term:
1. Extend the "Expression" to allow caller to specify allowed return types, automatically raising an error on type mismatch
2. (rejected) Allow the expression to return the possible return types. Can assist in optimizing, or type checking
3. Condition predicates (for expressions ?): not, empty, exists and bool (aggressive coercion)
4. Simple recursive - potentially search/filter
5. Named formatter

Rejected:
4. (rejected, combined isinstances are much faster) Type predicates `isarray`, `isobject`, `isscalar`, 
