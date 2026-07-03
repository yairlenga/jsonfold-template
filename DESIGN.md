# JSONFold Template Language (JFTL)

## Goal

Template language to generate JSON documents from (1) JSON Template (2) JSON Input.

## Template Structure

{
    body: { TEMPLATE-BODY },
    macro: {
        "macro1": { MACRO-BODY },
        "macro2": { MACRO-BODY },
        ...
    }
    data: {
        "item1": { JSON-DATA },
        "item2": { JSON-DATA },
        ...
    }
}

## Template Processing

The JSON output is the result of processing the template `body`, according to the following rules:

1. Scalars:
   - Each scalar is passed as-is
2. Arrays:
   - Each element is processed.
   - Each element whose value is NONE is ignored.
   - The output is an array of all remaining elements
3. Objects without execution tag - no '$' attribute.
   - Each keyword is processed
   - If the keyword is NONE, or if it is not a string, this KV pair is ignored
   - The value is processed
   - If the value is NONE, this KV pair is ignored
   - Otherwise, keyword/value is added to the output object.
   - The output is the object containing all elements.  
4. Objects with other execution tag.
   - Will be processed by the logic engine.

## Logic Engine

```json
{
    "$": true,
    "set": {
        "var1": "EXPR-1",
        "var2": "EXPR-2",
        ...
    },
    "if": "EXPR",
    "data": "EXPR",
    "foreach": {
        "key": "KEY-VAR",
        "item": "ITEM-VAR",
        "in": "EXPR",
    },
    "case": [
        { "when": "COND-1", "then": "EXPR-1" },
        { "when": "COND-2", "then": "EXPR-2" },
    ],
    "body": "EXPR",
    "transform": "MERGE|FLATTEN|NONE",
    "error": "EXPR",
}
```