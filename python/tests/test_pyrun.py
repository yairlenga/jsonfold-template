#! /usr/bin/python3 

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from template import Engine, create_engine


def test1():
    template = {
        "main": {
            "test1": "$pyrun: 1+2",
            "test2": "$pyrun: ','.join(['a',  'b', 'c', 'd', 'e'])",
        }
    }
    engine = create_engine()
    compiled, errors = engine.compile(template)
    print(compiled)
    result = engine.render(compiled, None)
    print(result)


test1()
