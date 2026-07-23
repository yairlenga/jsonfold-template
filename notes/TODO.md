0.3:
1. Undocument shape in foreach. 


0.4:

1. Navigation with JSON pointer
2. Navigation through objects methods ? Should be explicitly enabled
3. Add kind, `apiVersion`, and potentially schema to the top level
6. Type predicates `isarray`, `isobject`, `isscalar`, `isindex`, `isstring`, `isbool`, `isnumber`, `isint`, is null

7.  Named frames allowing reference to frame data - `foreach` block, lambda, (maybe, selected body)
8.  Iterators vs arrays.
9.  Recursion with lambdas: named lambdas, macro lambdas and labeled lambdas.
11. Reserve grammar for single argument function calls `foo:bar:baz` and `baz | bar | foo`
13. Fix handling of statements that evaluate to "null". They should return a reference to literal None. None will indicate no body.
14. Basic format for stringification of numbers - decimals, grouping, percent, 
15. Add condition specific prefixes: not: empty: null: array: object:, disallow plain values in condition.
16. Remove "shape" checks - after bundling it to condition.
17. 

Long Term:
1. Extend the "Expression" to allow caller to specify allowed return types, automatically raising an error on type mismatch
2. Allow the expression to return the possible return types. Can assist in optimizing, or type checking
3. Condition predicates (for expressions ?): not, empty, exists and bool (aggressive coercion)
4. Simple recursive - potentially search/filter
5. Named formatter
