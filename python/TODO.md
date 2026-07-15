1. Navigation shortcut enhancements:
- Data sets
  
2. Navigation with JSON pointer

3. Navigation through objects methods ? Should be explicitly enabled

5. Allow multiple documents to be processed when coming from stdin.

7. Add kind, `apiVersion`, and potentially schema to the top level

8 Extend `foreach` to support numeric ranges 

9. Condition predicates (for expressions ?): not, empty, exists and bool (aggressive coercion)

10. Type predicates `isarray`, `isobject`, `isscalar`, `isindex`, `isstring`, `isbool`, `isnumber`, `isint`, is null

11. Named frames allowing reference to frame data - `foreach` block, lambda, (maybe, selected body)
12. Iterators vs arrays.
13. Recursion with lambdas: named lambdas, macro lambdas and labeled lambdas.
14. Simple recursive - potentially search/filter
15. Reserve grammar for single argument function calls `foo:bar:baz` and `baz | bar | foo`
16. Fix logic to distinguish between Missing and Null in from_pairs, if needed ?
