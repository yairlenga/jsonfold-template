#! /usr/bin/python3 

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from template import create_engine


def test1():
    template = {
        "eval": {
            "1+2": "$pyeval= 1+2",
            "join(a-z)": "$pyeval= ','.join(['a',  'b', 'c', 'd', 'e'])",
        },
        "eval_var": {
            "$": True,
            "set": {
                "foo": 100,
                "bar": 200,
                "list": ['a',  'b', 'c', 'd', 'e'],
            },
            "out": {
                "foo+bar=": "$pyeval= foo + bar",
                "join(list)=": "$pyeval= ','.join(list)"
            }
        }
    }
    engine = create_engine(all_plugins=True)
    result, status, errors = engine.compile_and_render(template, None, main_only=True)
    assert status.ok and not errors
    print(result)


test1()
